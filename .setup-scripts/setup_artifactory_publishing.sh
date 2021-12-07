## python artifactory dependency
echo "Artifactory URL: $artifactory_url"
mkdir ~/.pip/ && touch ~/.pip/pip.conf
echo "[global]" > ~/.pip/pip.conf
echo "extra-index-url = https://$artifactory_user:$artifactory_password@$artifactory_url/api/pypi/pypi-local/simple" >> ~/.pip/pip.conf

touch ~/.pypirc
echo "[distutils]" > ~/.pypirc
echo "index-servers = local" >> ~/.pypirc
echo "[local]" >> ~/.pypirc
echo "repository: https://$artifactory_url/api/pypi/pypi-local/simple" >> ~/.pypirc
echo "username: $artifactory_user" >> ~/.pypirc
echo "password: $artifactory_password" >> ~/.pypirc
