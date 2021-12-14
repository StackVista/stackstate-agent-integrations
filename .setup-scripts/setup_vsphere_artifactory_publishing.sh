## python artifactory dependency
echo "Artifactory PyPI URL: $ARTIFACTORY_URL_PYPI"
mkdir ~/.pip/ && touch ~/.pip/pip.conf
echo "[global]" > ~/.pip/pip.conf
echo "extra-index-url = https://$artifactory_user:$artifactory_password@$ARTIFACTORY_URL_PYPI" >> ~/.pip/pip.conf
