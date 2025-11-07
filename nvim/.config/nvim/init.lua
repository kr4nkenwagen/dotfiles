-- bootstrap lazy.nvim, LazyVim and your plugins
require("config.lazy")
require("colorizer").setup()
vim.keymap.set("n", "<leader>uu", vim.cmd.UndotreeToggle)
