return {
  {
    "stevearc/conform.nvim",
    enabled = true,
  },
  {
    "norcalli/nvim-colorizer.lua",
    enabled = true,
  },
  {
    "mbbill/undotree",
    enabled = true,
  },
  {
    "ryanoasis/vim-devicons",
    enabled = true,
  },
  {
    "neovim/nvim-lspconfig",
    enabled = true,
  },
  {
    "HiPhish/rainbow-delimiters.nvim",
    enabled = true,
  },
  {
    "vhyrro/luarocks",
    priority = 1000,
    enabled = true,
  },
  {
    "nvim-mini/mini.ai",
    enabled = true,
  },
  {
    "Hoffs/omnisharp-extended-lsp.nvim",
    enabled = true,
  },
  {
    "hrsh7th/nvim-cmp",
    enabled = true,
  },
  {
    "hrsh7th/nvim-pasta",
    enabled = true,
  },
  {
    "nvim-lua/plenary.nvim",
    enabled = true,
  },
  {
    "nvim-treesitter/nvim-treesitter",
    opts = {
      ensure_installed = {
        "vim",
        "lua",
        "vimdoc",
        "html",
        "css",
      },
    },
    enabled = true,
  },
}
