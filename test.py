alpha_lower = "abcdefghijklmnopqrstuvwxyz"
alpha_upper = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

if alpha_lower.find('C') >= 0:
    print("found in lower")
else:
    print("not found in lower")

if alpha_upper.find('C') >= 0:
    print("found in upper")
else:
    print("not found in upper")