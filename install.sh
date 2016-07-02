#!/bin/bash

if [[ $EUID -eq 0 ]]; then
   echo "This script must not be run as root" 1>&2
   exit 1
fi

INSTALLPATH="/usr/local/bin"
TOOLPATH=$HOME/.stm32tool
TEMPLATES_DIR=$TOOLPATH/templates

echo "Installing STM32Tool in $INSTALLPATH"
sudo install -m 755 stm32tool.py $INSTALLPATH
sudo ln -f $INSTALLPATH/stm32tool.py $INSTALLPATH/stm32tool

echo "Installing common files in $TOOLPATH"
mkdir -p $TEMPLATES_DIR
cp -r common $TEMPLATES_DIR

echo "Done"
