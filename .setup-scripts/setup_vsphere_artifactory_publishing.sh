## python artifactory dependency
mkdir ~/.pip/ && touch ~/.pip/pip.conf
echo "[global]" > ~/.pip/pip.conf
echo "extra-index-url = https://$ARTIFACTORY_USER:$ARTIFACTORY_PASSWORD@$artifactory_url/artifactory/api/pypi/pypi-local/simple/simple" >> ~/.pip/pip.conf
