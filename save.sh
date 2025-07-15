#!/bin/sh
cp ~/.tmux.conf .tmux.conf
time=$(date +"%D %Ts")
git add *
git commit -m "[$time] automated changes"
git push
