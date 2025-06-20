 local settings = {
    -- every line should be same width without escaped \
    header = {
      type = "text",
      align = "center",
      fold_section = false,
      title = "Header",
      margin = 5,
      content = require("startup.headers").neovim_banner_header,
      highlight = "Statement",
      default_color = "",
      oldfiles_amount = 0,
    },
    header_2 = {
        type = "text",
        oldfiles_directory = false,
        align = "center",
        fold_section = false,
        title = "Quote",
        margin = 5,
        content = { "kr4nkenwagen" },
        highlight = "Constant",
        default_color = "",
        oldfiles_amount = 0,
    },
    -- name which will be displayed and command
    body = {
        type = "mapping",
        align = "center",
        fold_section = false,
        title = "Basic Commands",
        margin = 5,
        content = {
          {  " Find File", "Telescope find_files", "<leader>fa" },
          {   "󰍉 Find Word", "Telescope live_grep", "<leader>fw" },
          {   " File Browser", "Telescope file_browser", "<leader>e" },
          {   " New File", "lua require'startup'.new_file()", "<leader>b"}
        },
        highlight = "String",
        default_color = "",
        oldfiles_amount = 0,
    },
    body_2 = {
        type = "oldfiles",
        oldfiles_directory = true,
        align = "center",
        fold_section = false,
        title = "Oldfiles of Directory",
        margin = 5,
        content = {},
        highlight = "String",
        default_color = "#FFFFFF",
        oldfiles_amount = 5,
    },
    footer = {
        type = "text",
        oldfiles_directory = false,
        align = "center",
        fold_section = false,
        title = "",
        margin = 5,
        content = { "kr4nkenwagens nvim config" },
        highlight = "TSString",
        default_color = "#FFFFFF",
        oldfiles_amount = 0,
    },

    clock = {
        type = "text",
        content = function()
            local clock = " " .. os.date("%H:%M")
            local date = " " .. os.date("%d-%m-%y")
            return { clock, date }
        end,
        oldfiles_directory = false,
        align = "center",
        fold_section = false,
        title = "",
        margin = 5,
        highlight = "TSString",
        default_color = "#FFFFFF",
        oldfiles_amount = 10,
    },

    footer_2 = {
        type = "text",
        content = require("startup.functions").packer_plugins(),
        oldfiles_directory = false,
        align = "center",
        fold_section = false,
        title = "",
        margin = 5,
        highlight = "TSString",
        default_color = "#FFFFFF",
        oldfiles_amount = 10,
    },

    options = {
        after = function()
            require("startup.utils").oldfiles_mappings()
        end,
        mapping_keys = true,
        cursor_column = 0.5,
        empty_lines_between_mappings = true,
        disable_statuslines = true,
        paddings = { 2, 2, 2, 2, 2, 2, 2 },
    },
    colors = {
        background = "#1f2227",
        folded_section = "#56b6c2",
    },
    parts = {
        "header",
        "header_2",
        "body",
        "body_2",
        "footer",
        "clock",
        "footer_2",
    },
}
return settings
