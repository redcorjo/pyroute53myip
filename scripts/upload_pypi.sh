
#!/bin/bash
# Generated using pyarchetype template
# pip install pyarchetype
# git clone https://github.com/redcorjo/pyarchetype.git

BASE_DIR=$(dirname $0)/..
TWINE_CONFIG=$(dirname $0)/../.pypirc
PYTHON=python3.9
PACKAGE=pyroute53myip

cd ${BASE_DIR}

python -m build 2>/dev/null >/dev/null || python -m pip install --upgrade pip build

echo Reinstall module
python -m pip install --upgrade --force-reinstall dist/${PACKAGE}*whl

#echo Run tests
#python tests/test_pyroute53myip.py

#pyroute53myip -h

echo "Upload to pypi"
if test -e ${TWINE_CONFIG}
then
    chmod 600 ${TWINE_CONFIG}
    twine upload dist/${PACKAGE}* --config-file ${TWINE_CONFIG} 
else
    twine upload dist/*
fi

exit