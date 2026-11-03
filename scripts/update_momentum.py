"""Fetch aggregate counts only. Requires authenticated gh with read access to all sources."""
import argparse
import datetime as dt
import json
from pathlib import Path
import subprocess
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
ORGANIZATION = 'integral-xyz'
ZONE = ZoneInfo('America/Toronto')

def run_gh(arguments, operation):
    """Report actionable failures without copying private CLI output into reports."""
    try:
        result = subprocess.run(['gh', 'api', 'graphql', *arguments], check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as error:
        diagnostic = (error.stderr or '').lower()
        if 'rate limit' in diagnostic:
            reason = 'GitHub rate limit reached; retry after the limit resets'
        elif any(term in diagnostic for term in ('401', '403', 'authenticate', 'authentication', 'gh auth login', 'bad credentials', 'resource not accessible', 'could not resolve to', '404', 'not found')):
            reason = 'check GitHub CLI authentication and access to all organization repositories'
        elif any(term in diagnostic for term in ('timeout', 'timed out', 'connection', 'network', 'tls', 'dial tcp', 'resolve host')):
            reason = 'check the network connection to GitHub and retry'
        else:
            reason = f'GitHub CLI exited with status {error.returncode}; inspect authentication, access, and service availability'
        raise RuntimeError(f'{operation} failed: {reason}; leaving existing snapshot untouched') from None
    except FileNotFoundError:
        raise RuntimeError(f'{operation} failed: install the GitHub CLI and authenticate; leaving existing snapshot untouched') from None
    return json.loads(result.stdout)

def week_ranges(today):
    stop = today - dt.timedelta(days=today.weekday())
    first = stop - dt.timedelta(weeks=12)
    return [(first + dt.timedelta(weeks=i), first + dt.timedelta(weeks=i+1)) for i in range(12)]

def collect(today):
    inventory_query = 'query($endCursor:String) { organization(login:' + json.dumps(ORGANIZATION) + ') { repositories(first:100, after:$endCursor) { totalCount nodes { viewerPermission } pageInfo { hasNextPage endCursor } } } }'
    pages = run_gh(['--paginate', '--slurp', '-f', 'query=' + inventory_query], 'Repository inventory')
    if not pages or any(page.get('errors') for page in pages):
        raise RuntimeError('GitHub could not return complete repository inventory; leaving existing snapshot untouched')
    connections = [page['data']['organization']['repositories'] for page in pages]
    repositories = [node for connection in connections for node in connection['nodes']]
    repository_count = connections[0]['totalCount']
    if not repositories or any(not node or not node.get('viewerPermission') for node in repositories):
        raise RuntimeError('Missing source repository access; leaving existing snapshot untouched')
    if len(repositories) != repository_count or connections[-1]['pageInfo']['hasNextPage']:
        raise RuntimeError('Incomplete repository inventory; leaving existing snapshot untouched')
    queries = []
    ranges = week_ranges(today)
    for i, (start, stop) in enumerate(ranges):
        a = dt.datetime.combine(start, dt.time(), ZONE).isoformat()
        b = (dt.datetime.combine(stop, dt.time(), ZONE) - dt.timedelta(seconds=1)).isoformat()
        query = f'is:pr is:merged org:{ORGANIZATION} merged:{a}..{b}'
        queries.append(f'w{i}: search(type:ISSUE, query:{json.dumps(query)}, first:1) {{ issueCount }}')
    response = run_gh(['-f', 'query=query {' + ' '.join(queries) + '}'], 'Momentum query')
    if response.get('errors'):
        raise RuntimeError('GitHub could not return complete counts; leaving existing snapshot untouched')
    data = response['data']
    weeks = []
    for i, (start, stop) in enumerate(ranges):
        count = data[f'w{i}']['issueCount']
        if type(count) is not int or count < 0:
            raise ValueError('Invalid count')
        weeks.append({'start': str(start), 'end': str(stop - dt.timedelta(days=1)), 'merged': count})
    return {'asOf': str(today), 'timezone': 'America/Toronto', 'organization': ORGANIZATION, 'repositoryCount': repository_count, 'weeks': weeks}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--as-of', type=dt.date.fromisoformat, default=dt.datetime.now(ZONE).date())
    args = parser.parse_args()
    snapshot = collect(args.as_of)
    target = ROOT / 'profile/momentum.json'
    temporary = target.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(snapshot, indent=2) + '\n')
    temporary.replace(target)
    print('Updated twelve complete weeks of aggregate counts.')
