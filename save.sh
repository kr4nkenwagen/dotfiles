#!/bin/sh

cp ~/.tmux.conf .tmux.conf

git add *
git commit - "{date %D %T} - automated changes"
git push
