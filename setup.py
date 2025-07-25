from setuptools import setup, find_packages

setup(
    name='grok-cli',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'click',
        'langchain_core',
        'langchain',
        'langchain_openai',
        'langchain_community',
    ],
    entry_points={
        'console_scripts': [
            'grok_cli = grok_cli.cli:main',
        ],
    },
    author='Your Name',
    description='A CLI tool for interacting with xAI Grok 4',
    long_description=open('readme.md').read(),
    long_description_content_type='text/markdown',
)