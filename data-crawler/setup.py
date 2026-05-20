from setuptools import setup, find_packages

setup(
    name="data-crawler",
    version="1.0.0",
    author="",
    author_email="",
    description="基金数据爬虫项目",
    long_description="用于爬取基金数据并存储到数据库的爬虫项目",
    long_description_content_type="text/markdown",
    packages=find_packages(),
    install_requires=[
        "requests>=2.31.0",
        "pandas>=2.0.0",
        "sqlalchemy>=2.0.0",
        "pymysql>=1.0.0",
        "beautifulsoup4>=4.12.0"
    ],
    entry_points={
        'console_scripts': [
            'crawler=app.main:main'
        ]
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='==3.12.6'
)
