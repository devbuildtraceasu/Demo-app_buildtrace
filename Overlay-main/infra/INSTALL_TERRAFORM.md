# Installing Terraform on macOS

## Quick Installation

### Option 1: Using Homebrew (Recommended)

If you have Homebrew installed:

```bash
brew install terraform
```

Verify installation:
```bash
terraform --version
```

### Option 2: Manual Installation

1. **Download Terraform:**
   - Go to: https://developer.hashicorp.com/terraform/downloads
   - Download the macOS ARM64 version (for Apple Silicon) or AMD64 (for Intel)
   - Or use direct download:
     ```bash
     # For Apple Silicon (M1/M2/M3)
     wget https://releases.hashicorp.com/terraform/1.9.0/terraform_1.9.0_darwin_arm64.zip
     
     # For Intel Macs
     wget https://releases.hashicorp.com/terraform/1.9.0/terraform_1.9.0_darwin_amd64.zip
     ```

2. **Extract and Install:**
   ```bash
   # Extract
   unzip terraform_*.zip
   
   # Move to a directory in your PATH
   sudo mv terraform /usr/local/bin/
   
   # Or to your home directory
   mkdir -p ~/bin
   mv terraform ~/bin/
   echo 'export PATH="$HOME/bin:$PATH"' >> ~/.zshrc
   source ~/.zshrc
   ```

3. **Verify:**
   ```bash
   terraform --version
   ```

### Option 3: Using tfenv (Terraform Version Manager)

If you want to manage multiple Terraform versions:

```bash
# Install tfenv
brew install tfenv

# Install latest Terraform
tfenv install latest

# Use latest
tfenv use latest

# Verify
terraform --version
```

## Verify Installation

After installation, verify it works:

```bash
terraform --version
```

You should see output like:
```
Terraform v1.9.0
on darwin_arm64
```

## Check Your System

To determine which version you need:

```bash
# Check if you have Apple Silicon or Intel
uname -m
# arm64 = Apple Silicon (M1/M2/M3) - use ARM64 version
# x86_64 = Intel Mac - use AMD64 version
```

## After Installation

Once Terraform is installed, you can proceed:

```bash
cd Overlay-main/infra/terraform

# Initialize Terraform
terraform init

# Review the plan
terraform plan

# Apply (creates infrastructure)
terraform apply
```

## Troubleshooting

### "command not found" after installation

1. **Check if Terraform is in your PATH:**
   ```bash
   which terraform
   ```

2. **If not found, add to PATH:**
   ```bash
   # For Homebrew installation
   echo 'export PATH="/opt/homebrew/bin:$PATH"' >> ~/.zshrc
   source ~/.zshrc
   
   # Or for manual installation in ~/bin
   echo 'export PATH="$HOME/bin:$PATH"' >> ~/.zshrc
   source ~/.zshrc
   ```

3. **Verify:**
   ```bash
   terraform --version
   ```

### Permission Denied

If you get permission errors:

```bash
# Make sure Terraform is executable
chmod +x /usr/local/bin/terraform
# or
chmod +x ~/bin/terraform
```

### Homebrew Not Installed

If you don't have Homebrew:

```bash
# Install Homebrew first
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Then install Terraform
brew install terraform
```

## Requirements

Terraform requires:
- macOS 10.13 or later
- 64-bit processor
- Internet connection (for downloading providers)

## Next Steps

After Terraform is installed:
1. Ensure the Terraform state bucket exists (see `CREATE_STATE_BUCKET.md`)
2. Navigate to terraform directory: `cd Overlay-main/infra/terraform`
3. Run `terraform init`
4. Review and apply: `terraform plan` then `terraform apply`
