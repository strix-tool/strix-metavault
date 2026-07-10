"""Unit tests for the pure password_strength() helper (no external tools).

Run:  python test_password_strength.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import strix_metavault_core as mv  # noqa: E402

fails = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + ("  " + extra if extra else ""))
    if not cond:
        fails.append(name)


# Empty / too short -> not acceptable
for pw in ["", "a", "aA1", "short7!"]:
    score, label, acc, warns = mv.password_strength(pw)
    check(f"reject short {pw!r}", not acc, f"score={score} label={label}")

# 8+ chars but only one class -> below the 2-class acceptance floor
score, label, acc, warns = mv.password_strength("aaaaaaaa")
check("reject single-class 8-char", not acc, label)

# 8 chars, two classes -> acceptable but weak (score < 3)
score, label, acc, warns = mv.password_strength("abcdefG1")
check("accept minimal 8-char two-class", acc, f"score={score} label={label}")
check("minimal is weak (score<3)", score < 3, f"score={score}")

# Strong password -> acceptable, score >= 3, no warnings
score, label, acc, warns = mv.password_strength("Correct-Horse-9!Battery")
check("accept strong password", acc, f"score={score} label={label}")
check("strong scores >= 3", score >= 3, f"score={score}")
check("strong has no warnings", warns == [], repr(warns))

# Very strong (long + all four classes)
score, label, acc, warns = mv.password_strength("Tr0ub4dour&3xtra-Long_P@ssphrase!")
check("very strong scores 4", score == 4, f"score={score} label={label}")

# Whitespace is not counted as a symbol class
score, label, acc, warns = mv.password_strength("abcd efgh")  # 2 classes? only lower + space
check("whitespace not a class -> single class rejected", not acc, label)

# --------------------------------------------------------------------------- #
# output_ext validation (pure function): a caller-supplied archive extension is
# concatenated into the output path, so it must never carry a path separator or
# '..' that could escape the output directory.
# --------------------------------------------------------------------------- #
check("safe .7z ext preserved", mv._safe_output_ext(".7z") == ".7z")
check("empty ext falls back to .7z", mv._safe_output_ext("") == ".7z")
for evil in ["/../evil.7z", "..\\evil.7z", "../../etc/x", ".7z/../..",
             "a/b.7z", "x\\y", "\x00.7z"]:
    got = mv._safe_output_ext(evil)
    check(f"traversal ext neutralised {evil!r}",
          "/" not in got and "\\" not in got and ".." not in got
          and "\x00" not in got and got.startswith("."),
          f"-> {got!r}")
# a benign but non-whitelisted ext is sanitised to a plain dotted token
check("odd ext sanitised", mv._safe_output_ext(".zip") == ".zip")
check("spaces in ext sanitised",
      mv._safe_output_ext(". 7z") not in ("", None)
      and " " not in mv._safe_output_ext(". 7z"))

print()
if fails:
    print(f"{len(fails)} FAILED: {fails}")
    sys.exit(1)
print("ALL PASSWORD-STRENGTH TESTS PASSED")
