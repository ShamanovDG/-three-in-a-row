FROM kivy/buildozer:latest

USER root

RUN mkdir -p /opt/pin
RUN printf "pip<26\nsetuptools<81\nwheel<0.46\n" > /opt/pin/constraints.txt

ENV PIP_CONSTRAINT=/opt/pin/constraints.txt
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

RUN /home/user/.venv/bin/python -m pip install --upgrade "pip<26" "setuptools<81" "wheel<0.46"

RUN python3 - <<'PY'
from pathlib import Path

patched = []
for path in Path('/home/user').rglob('pythonforandroid/build.py'):
    text = path.read_text(encoding='utf-8', errors='ignore')

    changed = text.replace(
        "source venv/bin/activate && pip install -U pip",
        "source venv/bin/activate && python -m ensurepip --default-pip && python -m pip --version"
    ).replace(
        "source venv/bin/activate && pip install -U setuptools",
        "source venv/bin/activate && python -m pip --version"
    )

    if changed != text:
        path.write_text(changed, encoding='utf-8')
        patched.append(str(path))

print("\\n".join(patched) if patched else "NO_PATCH_TARGET_FOUND")
PY

WORKDIR /home/user/hostcwd