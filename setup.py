from setuptools import setup, find_packages

setup(
    name='runpal',
    version='0.1.0',
    description="A data container management tool to run jobs and avoid pipeline 'graveyards'",
    author="Rohan Khan, Alper Celik",
    author_email='alper.celik@sickkids.ca',
    packages=find_packages(),
    zip_safe=False,
    package_data={"": ["*.json"]},
    include_package_data=True
)
