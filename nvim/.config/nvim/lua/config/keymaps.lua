-- Keymaps are automatically loaded on the VeryLazy event
-- Default keymaps that are always set: https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/keymaps.lua
-- Add any additional keymaps here

vim.api.nvim_set_keymap('n', '<leader>dc', ':lua require"dap".continue()<CR>', { noremap = true })
vim.api.nvim_set_keymap('n', '<leader>do', ':lua require"dap".step_over()<CR>', { noremap = true })
vim.api.nvim_set_keymap('n', '<leader>di', ':lua require"dap".step_into()<CR>', { noremap = true })
vim.api.nvim_set_keymap('n', '<leader>du', ':lua require"dap".step_out()<CR>', { noremap = true })
vim.keymap.set("n", "<leader>uu", vim.cmd.UndotreeToggle)
local opts = { noremap = true, silent = true }
vim.api.nvim_set_keymap('n', '<Leader>db', "<cmd>lua require'dap'.toggle_breakpoint()<CR>", opts)
vim.api.nvim_set_keymap('n', '<Leader>dB', "<cmd>lua require'dap'.set_breakpoint(vim.fn.input('Breakpoint condition: '))<CR>", opts)
vim.api.nvim_set_keymap('n', '<Leader>dr', "<cmd>lua require'dap'.repl.open()<CR>", opts)
vim.api.nvim_set_keymap('n', '<Leader>dl', "<cmd>lua require'dap'.run_last()<CR>", opts)

vim.api.nvim_set_keymap('n', '<Leader>cD', "<cmd>Neogen<CR>", opts)
vim.api.nvim_set_keymap('n', '<Leader>oo', "<cmd>lua require('ollama').prompt()<CR>", opts)
vim.api.nvim_set_keymap('v', '<Leader>oo', "<cmd>lua require('ollama').prompt()<CR>", opts)


