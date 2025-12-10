require("config.lazy")
require("colorizer").setup()
local dap = require('dap')
local dapui = require('dapui')
dapui.setup()
require("nvim-dap-virtual-text").setup()
dap.listeners.after.event_initialized["dapui_config"] = function() dapui.open() end
dap.listeners.before.event_terminated["dapui_config"] = function() dapui.close() end
dap.listeners.before.event_exited["dapui_config"] = function() dapui.close() end
dap.adapters.cppgdb = {
  id = 'cppdbg',
  type = 'executable',
  command = vim.fn.stdpath('data') .. '/mason/packages/cpptools/extension/debugAdapters/bin/OpenDebugAD7',
}
require("ai-docstring").setup({
  key = "<leader>o",
  ai = {
    model = "codellama:latest"
  }
})

require("lspconfig").pyright.setup{
    settings = {
        python = {
            venvPath = ".",
            venv = ".venv",
        }
    }
}

local harpoon = require("harpoon")
harpoon:setup()

local function get_executable()
    local cwd = vim.fn.getcwd()
    local handle = io.popen('find ' .. cwd .. ' -maxdepth 1 -type f -executable')
    if handle == nil then
      return "a.out"
    end
    local result = handle:read("*a")
    handle:close()
    local files = {}
    for line in result:gmatch("[^\r\n]+") do
        if line ~= cwd then
            table.insert(files, line)
        end
    end
    if #files == 1 then
        return files[1]
    elseif #files > 1 then
        local choices = { "Select executable:" }
        for i, f in ipairs(files) do
            table.insert(choices, f)
        end
        local choice = vim.fn.inputlist(choices)
        return files[choice]
    else
        return "a.out"
    end
end

dap.configurations.c = {
  {
    name = "Launch with GDB",
    type = "cppgdb",
    request = "launch",
    program = get_executable(),
    cwd = '${workspaceFolder}',
    stopAtEntry = true,
    args = {},
    setupCommands = {
      {
        text = "-enable-pretty-printing",
        description = "Enable pretty printing",
        ignoreFailures = false
      }
    },
    MIMode = "gdb",
    miDebuggerPath = "/usr/bin/gdb",  -- Adjust if gdb is elsewhere
    runInTerminal = true,
  },
}
dap.configurations.cpp = dap.configurations.c
local servers = { "html", "cssls", "omnisharp", "c", "cpp" }
vim.lsp.enable(servers)
