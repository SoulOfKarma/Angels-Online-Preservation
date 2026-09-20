with open('../AO/Angel_unpacked.c', 'r', encoding='utf-8', errors='ignore') as f:
    for idx, line in enumerate(f):
        if 346000 <= idx <= 346600:
            if '*' in line and any(w in line for w in ('= 0x', '= 1', '= 2', '= 3', '= 4', '= 5', '= 6', '= 7', '= 8', '= 9', '= 10', '= 11', '= 12', '= 13', '= 14', '= 15', '= 16', '= 17', '= 18', '= 19', '= 20', '= 21', '= 22', '= 23', '= 24', '= 25', '= 26', '= 27', '= 28', '= 29', '= 30', '= 31', '= 32', '= 33', '= 34', '= 35', '= 36', '= 37', '= 38', '= 39', '= 40', '= 41', '= 42', '= 43', '= 44', '= 45')):
                print(f"{idx}: {line.strip()[:100]}")
            elif 'sub_81D190' in line:
                print(f"{idx}: ---> SEND PACKET")
