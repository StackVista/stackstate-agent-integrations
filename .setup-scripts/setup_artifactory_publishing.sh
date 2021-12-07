## python artifactory dependency
mkdir ~/.pip/ && touch ~/.pip/pip.conf
echo "[global]" > ~/.pip/pip.conf
echo "extra-index-url = https://$artifactory_user:$artifactory_password@$artifactory_url/artifactory/api/pypi/pypi-local/simple" >> ~/.pip/pip.conf

touch ~/.pypirc
echo "[distutils]" > ~/.pypirc
echo "index-servers = local" >> ~/.pypirc
echo "[local]" >> ~/.pypirc
echo "repository: https://$artifactory_url" >> ~/.pypirc
echo "username: $artifactory_user" >> ~/.pypirc
echo "password: $artifactory_password" >> ~/.pypirc
