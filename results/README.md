# Results Folder Guide

This folder explains runtime output locations.

Actual result data is written outside git tracking under these folders:

- C:\VScode\Yoshida_script\teacher_data
- C:\VScode\Yoshida_script\teacher_data_merged
- C:\VScode\Yoshida_script\shadowhand_action_dataset
- C:\VScode\Yoshida_script\pi0_action_eval
- C:\VScode\Yoshida_script\pi0_action_eval_merged
- C:\VScode\Yoshida_script\camera

These folders can be large, so they are ignored by git.

## Useful output files

From `shadowhand_action_dataset/<timestamp>/`:
- summary.json
- preview.txt
- action_debug.csv
- shadowhand_action_dataset.jsonl

From `pi0_action_eval_merged/<timestamp>/`:
- summary.json
- preview.txt
- pi0_eval_action_debug.csv
- pi0_eval_dataset.jsonl
