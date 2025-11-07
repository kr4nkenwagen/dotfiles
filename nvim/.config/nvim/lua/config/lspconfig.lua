require("lazy").setup({ "Hoffs/omnisharp-extended-lsp.nvim" })
local servers = { "html", "cssls", "omnisharp", "c", "cpp" }
vim.lsp.enable(servers)
