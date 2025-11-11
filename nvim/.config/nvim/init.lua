-- bootstrap lazy.nvim, LazyVim and your plugins
require("config.lazy")
require("colorizer").setup()

local dap = require('dap')
local dapui = require('dapui')

-- DAP UI setup (same as before)
dapui.setup()
require("nvim-dap-virtual-text").setup()

dap.listeners.after.event_initialized["dapui_config"] = function() dapui.open() end
dap.listeners.before.event_terminated["dapui_config"] = function() dapui.close() end
dap.listeners.before.event_exited["dapui_config"] = function() dapui.close() end

-- Adapter
dap.adapters.cppgdb = {
  id = 'cppdbg',
  type = 'executable',
  command = vim.fn.stdpath('data') .. '/mason/packages/cpptools/extension/debugAdapters/bin/OpenDebugAD7',
}

require("ai-docstring").setup({
        key = "<leader>od"
})

local function get_executable()
    local cwd = vim.fn.getcwd()
    local handle = io.popen('find ' .. cwd .. ' -maxdepth 1 -type f -executable')
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
        return vim.fn.input('Path to executable: ', cwd .. '/', 'file')
    end
end

-- Configuration
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

