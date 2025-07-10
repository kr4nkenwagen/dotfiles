require "nvchad.mappings"

-- add yours here

local map = vim.keymap.set

map("n", ";", ":", { desc = "CMD enter command mode" })
map("i", "jk", "<ESC>")
map("n", "<leader>tt", ":lua require('base46').toggle_transparency()<CR>", { noremap = true, silent = true, desc = "Toggle Background Transparency" })
map("n", "<leader>u", vim.cmd.UndotreeToggle, { noremap = true, silent = true, desc = "Undotree"})
if client and client.name == "omnisharp" then
  map("gd", require('omnisharp_extended').lsp_defintion, 'Go to Definition')
  map("gr", require('omnisharp_extended').lsp_reference, 'Go to Reference')
  map("gI", require('omnisharp_extended').lsp_implementation, "Go to Implementation")
  map("<leader>D", require('omnisharp_extended').lsp_type_defintion, 'Type Defintion')
  map('K', vim.lsp.buf.hover, 'Hover Documentation')

end

map('n', '<C-n>', require('pasta').config.next_key)
map('n', '<C-p>', require('pasta').config.prev_key)
  -- map({ "n", "i", "v" }, "<C-s>", "<cmd> w <cr>")
