#!/bin/bash
# Quick Terraform installation script for macOS

echo "Installing Terraform using Homebrew..."

# Check if Homebrew is installed
if ! command -v brew &> /dev/null; then
    echo "Error: Homebrew is not installed."
    echo "Install it first: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    exit 1
fi

# Install Terraform
brew install terraform

# Verify installation
if command -v terraform &> /dev/null; then
    echo ""
    echo "✅ Terraform installed successfully!"
    echo ""
    terraform --version
    echo ""
    echo "You can now run:"
    echo "  cd infra/terraform"
    echo "  terraform init"
else
    echo "❌ Installation may have failed. Please check the output above."
    exit 1
fi
