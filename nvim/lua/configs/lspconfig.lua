require("nvchad.configs.lspconfig").defaults()
require('lazy').setup({
  'Hoffs/omnisharp-extended-lsp.nvim'
})
local servers = { "html", "cssls", "omnisharp", "c", "cpp" }
vim.lsp.enable(servers)

-- read :h vim.lsp.config for changing options of lsp servers 
