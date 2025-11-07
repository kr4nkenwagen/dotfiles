-- Options are automatically loaded before lazy.nvim startup
-- Default options that are always set: https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/options.lua
-- Add any additional options here
vim.opt.relativenumber = true
vim.lsp.enable({ "html", "cssls", "omnisharp", "c", "cpp" })
vim.opt.showtabline = 0
vim.opt.cursorline = true
vim.opt.expandtab = true
vim.opt.tabstop = 2
vim.opt.autoread = true
vim.opt.splitright = true

