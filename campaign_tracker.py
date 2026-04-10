#!/usr/bin/env python3
"""Live campaign tracking - recursive search for live.json files."""

import time
import json
from pathlib import Path
from datetime import datetime
import subprocess
import sys

class FinalTracker:
    def __init__(self):
        self.log_file = Path("campaign_progress.log")
        self.results_dir = Path("results/eu_rc_vs_pinn_stage2/raw")
        self.cases = ['bestest_hydronic', 'bestest_hydronic_heat_pump', 'singlezone_commercial_hydronic', 'twozone_apartment_hydronic']
        self.start_time = datetime.now()
        self._write_header()
    
    def _write_header(self):
        header = "\n================================================================================\nCAMPAIGN LIVE TRACKER - 30-Day PINN Execution (Recursive Search)\n================================================================================\nStarted: {}\n\n================================================================================\nREAL-TIME LOG\n================================================================================\n\n".format(self.start_time.strftime('%Y-%m-%d %H:%M:%S'))
        self.log_file.write_text(header, encoding='utf-8')
    
    def _log(self, msg, level="INFO"):
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        line = "[{}] [{:8s}] {}".format(ts, level, msg)
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(line + "\n")
        print(line)
    
    def check_pinn(self):
        status = {'live': [], 'done': []}
        
        for case in self.cases:
            # Check for completed
            final = self.results_dir / case / 'pinn' / 'te_std_01.json'
            if final.exists():
                try:
                    with open(final, encoding='utf-8') as fp:
                        data = json.load(fp)
                    if data.get('n_steps') == 2880:
                        status['done'].append(case)
                        continue
                except:
                    pass
            
            # Check for live (recursive search)
            case_dir = self.results_dir / case / 'pinn'
            if case_dir.exists():
                for live_file in case_dir.rglob('te_std_01.live.json'):
                    try:
                        with open(live_file, encoding='utf-8') as fp:
                            data = json.load(fp)
                        recs = data.get('step_records', [])
                        pct = 100.0 * len(recs) / 2880 if recs else 0
                        t_zone = recs[-1].get('t_zone', 0) if recs else 0
                        status['live'].append({'case': case, 'progress': len(recs), 'pct': round(pct, 1), 'tz': round(t_zone, 2)})
                    except:
                        pass
                    break
        
        return status
    
    def monitor(self):
        check_interval = 300
        max_seconds = 24 * 3600
        elapsed = 0
        check_num = 0
        
        self._log("Starting monitor - checks every {}s, max {}h".format(check_interval, 24), "INFO")
        
        while elapsed < max_seconds:
            check_num += 1
            self._log("", "")
            self._log("Check #{} at {}".format(check_num, datetime.now().strftime('%H:%M:%S')), "CHECK")
            
            status = self.check_pinn()
            
            self._log("LIVE: {} cases | DONE: {} cases".format(len(status['live']), len(status['done'])), "STATUS")
            for item in status['live']:
                self._log("  [RUNNING] {}: {}/2880 ({:.1f}%) Tz={}C".format(item['case'][:30].ljust(30), item['progress'], item['pct'], item['tz']), "EXEC")
            for item in status['done']:
                self._log("  [COMPLETE] {}".format(item), "DONE")
            
            elapsed_t = datetime.now() - self.start_time
            h, r = divmod(int(elapsed_t.total_seconds()), 3600)
            m, s = divmod(r, 60)
            self._log("Elapsed: {}h {}m {}s | Total: {}/{} cases".format(h, m, s, len(status['done']), len(self.cases)), "TIME")
            
            if len(status['done']) == 4 and len(status['live']) == 0:
                self._log("ALL COMPLETE - Ready for analysis", "SUCCESS")
                return 0
            
            if elapsed + check_interval < max_seconds:
                self._log("Waiting {}s before next check...".format(check_interval), "WAIT")
                time.sleep(check_interval)
                elapsed += check_interval
            else:
                break
        
        self._log("TIMEOUT after {}h".format(24), "ERROR")
        return 1

if __name__ == '__main__':
    tracker = FinalTracker()
    print("\n" + "="*80)
    print("CAMPAIGN TRACKER - Monitoring PINN 30-Day Execution")
    print("="*80)
    print("Log: campaign_progress.log\n")
    sys.exit(tracker.monitor())
