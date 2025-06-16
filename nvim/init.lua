vim.opt.clipboard = "unnamedplus"
vim.g.base46_cache = vim.fn.stdpath "data" .. "/base46/"
vim.g.mapleader = " "

-- bootstrap lazy and all plugins
local lazypath = vim.fn.stdpath "data" .. "/lazy/lazy.nvim"

if not vim.uv.fs_stat(lazypath) then
  local repo = "https://github.com/folke/lazy.nvim.git"
  vim.fn.system { "git", "clone", "--filter=blob:none", repo, "--branch=stable", lazypath }
end

vim.opt.rtp:prepend(lazypath)

local lazy_config = require "configs.lazy"

-- load plugins
require("lazy").setup({
  {
    "NvChad/NvChad",
    lazy = false,
    branch = "v2.5",
    import = "nvchad.plugins",
  },
  {
    "echasnovski/mini.ai",
    version = "*" ,
  },
  {
    "HiPhish/rainbow-delimiters.nvim",
  },
  {
    "Hoffs/omnisharp-extended-lsp.nvim",
    lazy = false
  },
  {
    "hrsh7th/nvim-cmp",
    lazy = false
  },
  {
    "hrsh7th/nvim-pasta",
    lazy = false
  },
  {
    "jceb/vim-orgmode",
    lazy = false
  },
  {
    "startup-nvim/startup.nvim",
    config = function()
      require("startup").setup(require("configs.startup_nvim"))
    end
  },
  {
    "nvim-lua/plenary.nvim",
    lazy = false
  },
  { import = "plugins" },
}, lazy_config)

-- load theme
dofile(vim.g.base46_cache .. "defaults")
dofile(vim.g.base46_cache .. "statusline")

require "options"
require "nvchad.autocmds"
require("startup").setup()
require("mini.ai").setup()

vim.schedule(function()
  require "mappings"
end)
vim.lsp.enable('pyright')
