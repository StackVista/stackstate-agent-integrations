## python artifactory dependency
mkdir ~/.pip/ && touch ~/.pip/pip.conf
echo "[global]" > ~/.pip/pip.conf
echo "extra-index-url = https://$ARTIFACTORY_USER:$ARTIFACTORY_PASSWORD@$ARTIFACTORY_URL/artifactory/api/pypi/pypi-local/simple" >> ~/.pip/pip.conf

touch ~/.pypirc
echo "[distutils]" > ~/.pypirc
echo "index-servers = local" >> ~/.pypirc
echo "[local]" >> ~/.pypirc
echo "repository: https://$ARTIFACTORY_URL" >> ~/.pypirc
echo "username: $ARTIFACTORY_USER" >> ~/.pypirc
echo "password: $ARTIFACTORY_PASSWORD" >> ~/.pypirc
