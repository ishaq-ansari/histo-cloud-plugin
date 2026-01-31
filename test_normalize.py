#!/usr/bin/env python3
"""Test the normalization logic"""

def normalize_tf2_name(name):
    if name.endswith(':0'):
        name = name[:-2]
    
    if '/BatchNorm/' in name:
        bn_indices = []
        idx = 0
        while True:
            idx = name.find('/BatchNorm/', idx)
            if idx == -1:
                break
            bn_indices.append(idx)
            idx += 1
        
        if len(bn_indices) == 2:
            first_bn = bn_indices[0]
            second_bn = bn_indices[1]
            
            prefix = name[:first_bn]
            middle = name[first_bn+11:second_bn]
            suffix = name[second_bn+11:]
            
            print(f'Input: {name}')
            print(f'  prefix={repr(prefix)}')
            print(f'  middle={repr(middle)}')
            print(f'  suffix={repr(suffix)}')
            print(f'  match={middle == prefix}')
            
            if middle == prefix:
                return f'{prefix}/BatchNorm/{suffix}'
    
    return name

# Test cases
tests = [
    'aspp0/BatchNorm/aspp0/BatchNorm/beta:0',
    'aspp2_depthwise/BatchNorm/aspp2_depthwise/BatchNorm/beta:0',
    'xception_65/entry_flow/block1/unit_1/xception_module/separable_conv1_depthwise/BatchNorm/xception_65/entry_flow/block1/unit_1/xception_module/separable_conv1_depthwise/BatchNorm/beta:0'
]

for t in tests:
    result = normalize_tf2_name(t)
    print(f'Normalized: {result}')
    print()
