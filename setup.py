from setuptools import find_packages, setup


setup(
    name="codex-remoter",
    version="0.1.0",
    description="Control the Codex desktop app through CDP and expose a REST API",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "fastapi>=0.115,<1.0",
        "uvicorn[standard]>=0.30,<1.0",
        "websocket-client>=1.8,<2.0",
    ],
    extras_require={
        "dev": ["httpx>=0.27,<1.0", "pytest>=8,<10"],
    },
)
