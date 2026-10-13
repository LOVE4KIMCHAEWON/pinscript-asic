"""Record evidence only after every CI validation command has succeeded."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports'


def results(path):
    cases = ET.parse(path).getroot().findall('.//testcase')
    failed = sum(case.find('failure') is not None or case.find('error') is not None
                 for case in cases)
    skipped = sum(case.find('skipped') is not None for case in cases)
    assert cases and failed == 0 and skipped == 0, f'Non-passing results: {path}'
    return {'tests': len(cases), 'failures': failed, 'skipped': skipped}


def version(*command):
    return subprocess.check_output(command, text=True, stderr=subprocess.STDOUT).strip()


def main():
    REPORTS.mkdir(exist_ok=True)
    shutil.copyfile(ROOT / 'test/results-rtl.xml', REPORTS / 'rtl.xml')
    shutil.copyfile(ROOT / 'test/results-generic.xml', REPORTS / 'generic.xml')
    shutil.copyfile(ROOT / 'build/yosys_generic.log', REPORTS / 'yosys.log')
    source_sha = os.environ.get('GITHUB_SHA') or version('git', 'rev-parse', 'HEAD')
    run_url = (f"https://github.com/{os.environ['GITHUB_REPOSITORY']}/actions/runs/"
               f"{os.environ['GITHUB_RUN_ID']}")
    summary = {
        'source_commit': source_sha, 'run_url': run_url,
        'rtl_sha256': hashlib.sha256((ROOT / 'src/project.v').read_bytes()).hexdigest(),
        'netlist_sha256': hashlib.sha256((ROOT / 'build/netlist_generic.v').read_bytes()).hexdigest(),
        'suites': {name: results(REPORTS / f'{name}.xml')
                   for name in ['software', 'rtl', 'generic']},
        'tools': {'yosys': version('yosys', '-V'),
                  'iverilog': version('iverilog', '-V').splitlines()[0],
                  'verilator': version('verilator', '--version'),
                  'python': version('python', '--version'),
                  'cocotb': version('cocotb-config', '--version')},
        'scope': 'Generic synthesis and functional simulation; no PDK mapping, STA, GDS or place-and-route.'
    }
    (REPORTS / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    lines = [
        '# Executed verification results', '',
        f"Source commit: `{source_sha}`", '', f'[GitHub Actions run]({run_url})', '',
        '| Suite | Passed | Failed | Skipped |', '| --- | ---: | ---: | ---: |'
    ]
    for name, suite in summary['suites'].items():
        lines.append(f"| {name} | {suite['tests']} | {suite['failures']} | {suite['skipped']} |")
    lines += ['', 'Yosys completed `hierarchy -check`, `synth`, and `check -assert`.', '',
              'The RTL and synthesized netlist passed the same external-pin test suite. '
              'This is regression evidence for tested scenarios, not a formal equivalence proof.', '',
              f"Netlist SHA-256: `{summary['netlist_sha256']}`", '',
              f"RTL SHA-256: `{summary['rtl_sha256']}`", '', '## Tool versions', '']
    lines += [f'- {name}: `{value}`' for name, value in summary['tools'].items()]
    lines += ['', summary['scope'], '', 'See `yosys.log` for warnings and generic cell statistics.', '']
    (REPORTS / 'latest.md').write_text('\n'.join(lines))
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
