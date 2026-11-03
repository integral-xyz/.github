import datetime as dt
import json
import subprocess
import unittest
from unittest.mock import patch

from update_momentum import collect, week_ranges


def inventory(permission='READ'):
    return [{'data': {'organization': {'repositories': {'totalCount': 1, 'nodes': [{'viewerPermission': permission}], 'pageInfo': {'hasNextPage': False, 'endCursor': None}}}}}]

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
        run.side_effect = [result(inventory()), result({'data': data})]
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
        run.side_effect = [result(inventory()), result({'errors': [{'message': 'failure'}], 'data': {}})]
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
        run.side_effect = [result(pages), result({'data': {f'w{i}': {'issueCount': 5} for i in range(12)}})]
        snapshot = collect(dt.date(2026, 11, 9))
        self.assertEqual(snapshot['repositoryCount'], 2)
        self.assertIn('--paginate', run.call_args_list[0].args[0])
        self.assertIn('--slurp', run.call_args_list[0].args[0])


if __name__ == '__main__':
    unittest.main()
