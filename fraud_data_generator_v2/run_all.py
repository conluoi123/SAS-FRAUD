from generators.engine import ORDER, gen

for t in ORDER:
    gen(t)
    print("[OK]", t)
