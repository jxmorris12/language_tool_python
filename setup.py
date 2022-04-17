from setuptools import setup, find_packages

from os import path
this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='language_tool_python',
    version='2.7.1',
    description='Checks grammar using LanguageTool.',
    long_description_content_type='text/markdown',
    long_description=long_description,
    author='Jack Morris',
    author_email='jxmorris12@gmail.com',
    url='https://github.com/jxmorris12/language_tool_python',
    license='GNU GPL',
    packages=find_packages(),
    install_requires=open('requirements.txt').readlines(),
)
