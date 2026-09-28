#!/bin/sh
# Adds Graysons Wallet and Frostoise to the desktop menu, and all three commands
# (graysons-wallet, frostoise, qoinage) to ~/.local/bin.
set -e
HERE="$(dirname "$(readlink -f "$0")")"
mkdir -p "$HOME/.local/share/applications" "$HOME/.local/bin"
ln -sf "$HERE/graysons-wallet" "$HOME/.local/bin/graysons-wallet"
ln -sf "$HERE/frostoise" "$HOME/.local/bin/frostoise"
ln -sf "$HERE/qoinage" "$HOME/.local/bin/qoinage"
cat > "$HOME/.local/share/applications/graysons-wallet.desktop" <<D
[Desktop Entry]
Type=Application
Name=Graysons Wallet
Comment=Qoin wallet
Exec=$HERE/graysons-wallet
Icon=$HERE/icon.svg
Terminal=false
Categories=Finance;
D
cat > "$HOME/.local/share/applications/frostoise.desktop" <<D
[Desktop Entry]
Type=Application
Name=Frostoise
Comment=Qoin wallet miner
Exec=$HERE/frostoise
Icon=$HERE/icon.svg
Terminal=false
Categories=Finance;
D
echo "Installed. Look for Graysons Wallet and Frostoise in your app menu, or run: graysons-wallet / frostoise. Run the Qoinage vault from a terminal: qoinage --wallet <vault>"
