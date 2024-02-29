#!/bin/bash

ps -Af | grep start_ui.py | grep -v grep | awk '{print $2}' | xargs kill -9
