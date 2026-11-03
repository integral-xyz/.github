import datetime as dt
import json
from pathlib import Path
import runpy
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from update_momentum import collect, week_ranges


def inventory(permission='READ'):
    return [{'data': {'organization': {'repositories': {'totalCount': 1, 'nodes': [{'viewerPermission': permission}], 'pageInfo': {'hasNextPage': False, 'endCursor': None}}}}}]

def organization(public=0, nonpublic=1):
    return {'public_repos': public, 'owned_private_repos': nonpublic}


def result(payload):
    return subprocess.CompletedProcess([], 0, json.dumps(payload))


class MomentumTests(unittest.TestCase):
    def test_monday_excludes_incomplete_week(self):
        ranges = week_ranges(dt.date(2026, 11, 9))
        self.assertEqual(ranges[-1], (dt.date(2026, 11, 2), dt.date(2026, 11, 9)))
        self.assertEqual(len(ranges), 12)

    def test_sunday_does_not_count_partial_week(self):
        self.assertEqual(week_ranges(dt.date(2026, 11, 8))[-1][1], dt.date(2026, 11, 2))

    @patch('update_momentum.subprocess.run')
    def test_dst_boundaries_and_zero_counts(self, run):
        data = {f'w{i}': {'issueCount': 0} for i in range(12)}
        run.side_effect = [result(inventory()), result(organization()), result({'data': data})]
        snapshot = collect(dt.date(2026, 11, 9))
        query = run.call_args.args[0][-1]
        self.assertIn('2026-10-26T00:00:00-04:00..2026-11-01T23:59:59-05:00', query)
        self.assertEqual(snapshot['weeks'][-1]['merged'], 0)
        self.assertIn('org:integral-xyz', query)
        self.assertNotIn('repo:', query)
        self.assertNotIn('repositories', snapshot)
        self.assertEqual(snapshot['repositoryCount'], 1)

    @patch('update_momentum.subprocess.run')
    def test_missing_repository_access_fails(self, run):
        run.return_value = result(inventory(permission=None))
        with self.assertRaisesRegex(RuntimeError, 'Missing source repository access'):
            collect(dt.date(2026, 11, 9))

    @patch('update_momentum.subprocess.run')
    def test_partial_graphql_failure_fails(self, run):
        run.side_effect = [result(inventory()), result(organization()), result({'errors': [{'message': 'failure'}], 'data': {}})]
        with self.assertRaisesRegex(RuntimeError, 'complete counts'):
            collect(dt.date(2026, 11, 9))

    @patch('update_momentum.subprocess.run')
    def test_incomplete_inventory_fails(self, run):
        pages = inventory()
        pages[0]['data']['organization']['repositories']['totalCount'] = 2
        run.return_value = result(pages)
        with self.assertRaisesRegex(RuntimeError, 'Incomplete repository inventory'):
            collect(dt.date(2026, 11, 9))

    @patch('update_momentum.subprocess.run')
    def test_paginated_inventory_includes_all_repositories(self, run):
        pages = inventory() + inventory()
        for page in pages:
            page['data']['organization']['repositories']['totalCount'] = 2
        pages[0]['data']['organization']['repositories']['pageInfo']['hasNextPage'] = True
        run.side_effect = [result(pages), result(organization(nonpublic=2)), result({'data': {f'w{i}': {'issueCount': 5} for i in range(12)}})]
        snapshot = collect(dt.date(2026, 11, 9))
        self.assertEqual(snapshot['repositoryCount'], 2)
        self.assertIn('--paginate', run.call_args_list[0].args[0])
        self.assertIn('--slurp', run.call_args_list[0].args[0])

    @patch('update_momentum.subprocess.run')
    def test_consistently_filtered_inventory_fails_before_count_query(self, run):
        run.side_effect = [result(inventory()), result(organization(nonpublic=2))]
        with self.assertRaisesRegex(RuntimeError, 'does not match the organization-wide total'):
            collect(dt.date(2026, 11, 9))
        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args.args[0], ['gh', 'api', 'orgs/integral-xyz'])

    @patch('update_momentum.subprocess.run')
    def test_missing_or_invalid_authority_fails_closed(self, run):
        for authority in ({'public_repos': 1}, {'public_repos': 1, 'owned_private_repos': None},
                          {'public_repos': 1, 'owned_private_repos': -1},
                          {'public_repos': True, 'owned_private_repos': 0},
                          {'public_repos': 1, 'owned_private_repos': '0'}):
            with self.subTest(authority=authority):
                run.reset_mock()
                run.side_effect = [result(inventory()), result(authority)]
                with self.assertRaisesRegex(RuntimeError, 'owner-authorized organization metadata is required'):
                    collect(dt.date(2026, 11, 9))
                self.assertEqual(run.call_count, 2)

    @patch('update_momentum.subprocess.run')
    def test_internal_repositories_use_owned_nonpublic_total(self, run):
        authority = {**organization(), 'total_private_repos': 0}
        run.side_effect = [result(inventory()), result(authority), result({'data': {f'w{i}': {'issueCount': 0} for i in range(12)}})]
        self.assertEqual(collect(dt.date(2026, 11, 9))['repositoryCount'], 1)

    @patch('update_momentum.subprocess.run')
    def test_public_only_organization_accepts_zero_nonpublic_repositories(self, run):
        run.side_effect = [result(inventory()), result(organization(public=1, nonpublic=0)), result({'data': {f'w{i}': {'issueCount': 0} for i in range(12)}})]
        self.assertEqual(collect(dt.date(2026, 11, 9))['repositoryCount'], 1)

    @patch('update_momentum.subprocess.run')
    def test_authority_access_failure_stops_before_count_query(self, run):
        run.side_effect = [result(inventory()), subprocess.CalledProcessError(
            1, ['gh'], stderr='HTTP 403: Resource not accessible; private-example',
        )]
        with self.assertRaisesRegex(RuntimeError, 'Organization repository total failed') as raised:
            collect(dt.date(2026, 11, 9))
        self.assertNotIn('private-example', str(raised.exception))
        self.assertEqual(run.call_count, 2)

    def test_filtered_inventory_leaves_last_good_snapshot_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'scripts').mkdir()
            (root / 'profile').mkdir()
            script = root / 'scripts/update_momentum.py'
            shutil.copy(Path(__file__).with_name('update_momentum.py'), script)
            snapshot = root / 'profile/momentum.json'
            snapshot.write_text('{"lastGoodSnapshot": true}\n')
            before = snapshot.read_bytes()
            with patch('subprocess.run', side_effect=[result(inventory()), result(organization(nonpublic=2))]), patch('sys.argv', [str(script), '--as-of', '2026-11-03']):
                with self.assertRaisesRegex(RuntimeError, 'does not match the organization-wide total'):
                    runpy.run_path(str(script), run_name='__main__')
            self.assertEqual(snapshot.read_bytes(), before)
            self.assertFalse(snapshot.with_suffix('.json.tmp').exists())

    @patch('update_momentum.subprocess.run')
    def test_inventory_auth_failure_is_actionable_without_raw_stderr(self, run):
        run.side_effect = subprocess.CalledProcessError(
            1, ['gh'], stderr='HTTP 401: Bad credentials; private-example ghp_example',
        )
        with self.assertRaisesRegex(RuntimeError, 'Repository inventory failed.*authentication') as raised:
            collect(dt.date(2026, 11, 9))
        self.assertNotIn('private-example', str(raised.exception))
        self.assertNotIn('ghp_example', str(raised.exception))
        self.assertTrue(raised.exception.__suppress_context__)

    @patch('update_momentum.subprocess.run')
    def test_count_query_network_failure_is_actionable_without_raw_stderr(self, run):
        run.side_effect = [result(inventory()), result(organization()), subprocess.CalledProcessError(
            1, ['gh'], stderr='Connection timed out: https://private-example.invalid/?token=example',
        )]
        with self.assertRaisesRegex(RuntimeError, 'Momentum query failed.*network connection') as raised:
            collect(dt.date(2026, 11, 9))
        self.assertNotIn('private-example', str(raised.exception))
        self.assertIn('leaving existing snapshot untouched', str(raised.exception))

    @patch('update_momentum.subprocess.run')
    def test_rate_limit_failure_names_the_recovery(self, run):
        run.side_effect = subprocess.CalledProcessError(1, ['gh'], stderr='HTTP 403: API rate limit exceeded')
        with self.assertRaisesRegex(RuntimeError, 'rate limit reached; retry'):
            collect(dt.date(2026, 11, 9))

    @patch('update_momentum.subprocess.run')
    def test_missing_cli_explains_installation(self, run):
        run.side_effect = FileNotFoundError('gh')
        with self.assertRaisesRegex(RuntimeError, 'install the GitHub CLI'):
            collect(dt.date(2026, 11, 9))


if __name__ == '__main__':
    unittest.main()
