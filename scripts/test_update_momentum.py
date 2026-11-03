import datetime as dt
import json
import subprocess
import unittest
from unittest.mock import patch

from update_momentum import REPOS, ZONE, collect, week_ranges


class MomentumTests(unittest.TestCase):
    def test_monday_excludes_incomplete_week(self):
        ranges = week_ranges(dt.date(2026, 11, 9))
        self.assertEqual(ranges[-1], (dt.date(2026, 11, 2), dt.date(2026, 11, 9)))
        self.assertEqual(len(ranges), 12)

    def test_sunday_does_not_count_partial_week(self):
        self.assertEqual(week_ranges(dt.date(2026, 11, 8))[-1][1], dt.date(2026, 11, 2))

    @patch('update_momentum.subprocess.run')
    def test_dst_boundaries_and_zero_counts(self, run):
        data = {f'r{i}': {'name': repo, 'viewerPermission': 'READ'} for i, repo in enumerate(REPOS)}
        data.update({f'w{i}': {'issueCount': 0} for i in range(12)})
        run.return_value = subprocess.CompletedProcess([], 0, json.dumps({'data': data}))
        snapshot = collect(dt.date(2026, 11, 9))
        query = run.call_args.args[0][-1]
        self.assertIn('2026-10-26T00:00:00-04:00..2026-11-01T23:59:59-05:00', query)
        self.assertEqual(snapshot['weeks'][-1]['merged'], 0)

    @patch('update_momentum.subprocess.run')
    def test_missing_repository_access_fails(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, json.dumps({'data': {'r0': None}}))
        with self.assertRaisesRegex(RuntimeError, 'Missing source repository access'):
            collect(dt.date(2026, 11, 9))

    @patch('update_momentum.subprocess.run')
    def test_partial_graphql_failure_fails(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, json.dumps({'errors': [{'message': 'failure'}], 'data': {}}))
        with self.assertRaisesRegex(RuntimeError, 'complete counts'):
            collect(dt.date(2026, 11, 9))


if __name__ == '__main__':
    unittest.main()
