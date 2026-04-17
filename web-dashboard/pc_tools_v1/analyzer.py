#!/usr/bin/env python3
"""
Automatic crash cause analysis
"""

import json
from typing import Dict, List
from database import CrashDatabase
from decoder import AddressDecoder

class CrashAnalyzer:
    # constructor
    def __init__(self, db_path: str = "crash_dumps.db", 
                 executable_path: str = None):#path to the compiled program
        ## Create a CrashDatabase object to access crash data
        self.db = CrashDatabase(db_path)
        ## Create an AddressDecoder object : used to translate addresses into function names
        self.decoder = AddressDecoder(executable_path) if executable_path else None # only if exists (is not empty), so we create the decoder.

        
    ####     analyzes a list of crashes
    def analyze_pattern(self, crashes: List[Dict]) -> Dict:
        """Analyze recurring crash patterns"""
        #Initialization of structures
        patterns = {
            'most_common_file': {},
            'most_common_function': {},
            'severity_distribution': {},
            'time_patterns': {},
            'memory_correlation': []
        }
        ## Count how many times each file appears in the crashes.
        for crash in crashes:
            # Most frequent file
            file = crash.get('file', 'unknown')
            patterns['most_common_file'][file] = \
                patterns['most_common_file'].get(file, 0) + 1
            
            # Count how many crashes per severity.
            severity = crash.get('severity', 'unknown')
            patterns['severity_distribution'][severity] = \
                patterns['severity_distribution'].get(severity, 0) + 1
            
            # Calculates the percentage of memory used at the time of the crash.
            mem_usage = crash.get('memory_used_kb', 0)
            mem_total = crash.get('memory_total_kb', 1)
            mem_percent = (mem_usage / mem_total) * 100 if mem_total > 0 else 0
            
            #Saves memory information
            patterns['memory_correlation'].append({
                'timestamp': crash.get('timestamp'),
                'memory_percent': mem_percent,
                'severity': severity
            })
        
        # Sort most common files by frequency (top 10)
        patterns['most_common_file'] = dict(
            sorted(patterns['most_common_file'].items(), 
                   key=lambda x: x[1], reverse=True)[:10]
        )
        
        return patterns
    
    def generate_report(self, output_path: str = "crash_report.json"):
        """Generate a complete crash analysis report"""
        crashes = self.db.get_all_crashes(limit=1000)
        stats = self.db.get_statistics()
        patterns = self.analyze_pattern(crashes)
        
        report = {
            'summary': {
                'total_crashes': stats.get('total_crashes', 0),
                'analysis_date': datetime.now().isoformat(),
                'date_range': {
                    'from': crashes[-1]['timestamp'] if crashes else None,
                    'to': crashes[0]['timestamp'] if crashes else None
                }
            },
            'statistics': stats,
            'patterns': patterns,
            'recommendations': self._generate_recommendations(patterns),
            'top_crashes': crashes[:10]
        }
        
        # Save report to JSON file
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        return report
    
    def _generate_recommendations(self, patterns: Dict) -> List[str]:
        """Generate recommendations based on crash patterns"""
        recommendations = []
        
        #Recommendation #1 - Most Crashed File
        if patterns['most_common_file']:  # dic {"main.cpp": 2, ...}
            top_file = list(patterns['most_common_file'].keys())[0]
            recommendations.append( # add recommendation
                f"High priority: Check file {top_file} "#insert value of top_file :"main.cpp"
                f"({patterns['most_common_file'][top_file]} crashes)"#insert nb of crash:2
            )# recommendations = [    "High priority: Check file main.cpp (2 crashes)"]
        
        # Recommendation #2 - Critical Crashes
        critical_count = patterns['severity_distribution'].get('CRITICAL', 0)#get value "..."from dic
        if critical_count > 5: #If more than 5 crashes occur, it's a CRITICAL situation → urgent situation
            recommendations.append(
                f"Alert: {critical_count} CRITICAL crashes detected - "
                "Urgent code review recommended"
            )
        
        # create list   contains only crashes where memory usage  90%.
        high_mem_crashes = [ 
            c for c in patterns['memory_correlation'] 
            if c['memory_percent'] > 90
        ]
        #If more than 3 crashes   → a problem is suspected
        if len(high_mem_crashes) > 3:
            recommendations.append(
                f"Warning: {len(high_mem_crashes)} crashes with memory usage > 90% - "
                "Check for memory leaks"
            )
        
        return recommendations

if __name__ == "__main__":
  
    analyzer = CrashAnalyzer(
        db_path="crash_dumps.db",
        executable_path="../embedded/Build/CoreDumpApp"
    )
    
    report = analyzer.generate_report("crash_analysis_report.json")
    print(f"Report generated: {len(report['recommendations'])} recommendations")
