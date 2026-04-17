#!/usr/bin/env python3
"""
Decode addresses using addr2line
"""

import subprocess
import re
from typing import List, Tuple, Optional

class AddressDecoder:
    def __init__(self, executable_path: str):
        # Save the path of the program (executable) we want to analyze
        self.executable_path = executable_path
    
    def decode_address(self, address: str) -> Tuple[Optional[str], Optional[str], Optional[int]]:
        """
        Decode one address into function name, file, and line number
        Returns: (function_name, file_path, line_number)
        """
        try:
            # Clean the address (remove "0x" if present)
            addr = address.replace('0x', '').replace('0X', '')
            
            # Run addr2line tool to decode the address
            result = subprocess.run(
                ['addr2line', '-f', '-C', '-e', self.executable_path, f'0x{addr}'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            # If command worked
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) >= 2:
                    function = lines[0]   # function name
                    location = lines[1]   # file:line
                    
                    # Try to split file and line number
                    match = re.match(r'(.+):(\d+)', location)
                    if match:
                        file_path = match.group(1)
                        line_number = int(match.group(2))
                        return function, file_path, line_number
                    
                    # If no line number found, return file only
                    return function, location, None
            
            # If decoding failed
            return "???", "???", None
            
        except Exception as e:
            # If error happened, return error message
            return f"Error: {str(e)}", None, None
    
    def decode_stack(self, addresses: List[str]) -> List[Dict]:
        """Decode a full call stack (list of addresses)"""
        decoded_stack = []
        
        for idx, addr in enumerate(addresses):
            func, file, line = self.decode_address(addr)
            decoded_stack.append({
                'frame': idx,       # position in stack
                'address': addr,    # raw address
                'function': func,   # decoded function
                'file': file,       # decoded file
                'line': line        # decoded line
            })
        
        return decoded_stack
    
    def decode_json_file(self, json_path: str, output_path: Optional[str] = None):
        """Decode crash dump JSON file and add decoded stack"""
        import json
        
        # Load crash dump JSON
        with open(json_path, 'r') as f:
            crash_data = json.load(f)
        
        # Decode call stack addresses
        call_stack = crash_data.get('call_stack', [])
        decoded_stack = self.decode_stack(call_stack)
        
        # Add decoded stack to crash data
        crash_data['decoded_call_stack'] = decoded_stack
        
        # If output file is given, save updated JSON
        if output_path:
            with open(output_path, 'w') as f:
                json.dump(crash_data, f, indent=2)
        
        return crash_data
