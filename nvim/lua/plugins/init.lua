return {
  {
    "stevearc/conform.nvim",
    -- event = 'BufWritePre', -- uncomment for format on save
    opts = require "configs.conform",
    lazy = false,
  },
  {
    "ryanoasis/vim-devicons",
    lazy = false,
  },
  {
    "mbbill/undotree",
    enabled = true,
    lazy = false,
  },
  -- These are some examples, uncomment them if you want to see them work!
  {
    "neovim/nvim-lspconfig",
    config = function()
      require "configs.lspconfig"
    end,
    lazy = false,
  },
  {
    "HiPhish/rainbow-delimiters.nvim",
    enabled = true,
    lazy = false,
  },
  {
    "vhyrro/luarocks.nvim",
    priority = 1000,
    config = true,
    lazy = false,
  },
  {
    "echasnovski/mini.ai",
    version = "*" ,
    lazy = false,
  },
  {
    "NvChad/NvChad",
    lazy = false,
    branch = "v2.5",
    import = "nvchad.plugins",
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
    end,
    lazy = true,
  },
  {
    "nvim-lua/plenary.nvim",
    lazy = false
  }

  -- test new blink
  -- { import = "nvchad.blink.lazyspec" },

  -- {
  -- 	"nvim-treesitter/nvim-treesitter",
  -- 	opts = {
  -- 		ensure_installed = {
  -- 			"vim", "lua", "vimdoc",
  --      "html", "css"
  -- 		},
  -- 	},
  -- },
}
