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



vim.api.nvim_set_keymap('n', '<Leader>pr', "<cmd>PIO run<CR>", { desc = "PIO run"})
vim.api.nvim_set_keymap('n', '<Leader>pe', "<cmd>PIO env<CR>", { desc = "PIO env"})
vim.api.nvim_set_keymap('n', '<Leader>pc', "<cmd>PIO check<CR>", { desc = "PIO check"})
vim.api.nvim_set_keymap('n', '<Leader>po', "<cmd>PIO compiledb<CR>", { desc = "PIO compiledb"})
vim.api.nvim_set_keymap('n', '<Leader>pu', "<cmd>PIO upload<CR>", { desc = "PIO upload"})
vim.api.nvim_set_keymap('n', '<Leader>pp', "<cmd>PIO uploadfs<CR>", { desc = "PIO uploadfs"})
vim.api.nvim_set_keymap('n', '<Leader>pm', "<cmd>PIO monitor<CR>", { desc = "PIO monitor"})
vim.api.nvim_set_keymap('n', '<Leader>pb', "<cmd>PIO buildfs<CR>", { desc = "PIO buildfs"})

vim.keymap.set("n", "<leader>a", function() require("harpoon"):list():add() end)
vim.keymap.set("n", "<C-e>", function() require("harpoon").ui:toggle_quick_menu(harpoon:list()) end)
vim.keymap.set("n", "<C-h>", function() require("harpoon"):list():select(1) end)
vim.keymap.set("n", "<C-t>", function() require("harpoon"):list():select(2) end)
vim.keymap.set("n", "<C-n>", function() require("harpoon"):list():select(3) end)
vim.keymap.set("n", "<C-s>", function() require("harpoon"):list():select(4) end)
vim.keymap.set("n", "<C-S-P>", function() require("harpoon"):list():prev() end)
vim.keymap.set("n", "<C-S-N>", function() require("harpoon"):list():next() end)

