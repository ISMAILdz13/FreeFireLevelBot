from setuptools import setup, find_packages

setup(
    name="ff-like-bot-pro",
    version="2.0.0",
    description="Production-grade Free Fire Like Bot for MENA Server",
    author="FFBot Team",
    python_requires=">=3.10",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "httpx[http2]>=0.27.0",
        "pycryptodome>=3.20.0",
        "protobuf>=5.26.0",
        "aiosqlite>=0.20.0",
        "pyyaml>=6.0.1",
        "pydantic>=2.7.0",
        "rich>=13.7.0",
        "typer>=0.12.0",
        "anyio>=4.3.0",
        "asyncio-throttle>=1.0.2",
    ],
    entry_points={
        "console_scripts": [
            "ffbot=main:app",
        ],
    },
)
