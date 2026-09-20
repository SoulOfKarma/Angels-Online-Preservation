function Test()
  window.trace("Begin lua function Test()")
  
  window.msgbox("Hello1")
  window.msgbox("Hello2", mbYesNo)
  window.trace("End lua function Test()")
end

function Test_OnLock(dwID, dwCmdID, dwParam, pParam)
  local str
  str = string.format("OnLock %x %x %x %x", dwID, dwCmdID, dwParam, pParam)
  window.trace(str)
  window.trace("OnLock")
  return 1
end

function Test_OnHelp(dwID, dwCmdID, dwParam, pParam)
  window.trace("OnHelp")
  return 1
end

function TestMiniGame_OnClose(dwID, dwCmdID, dwParam, pParam)
  game.leave()
  return 1
end

function Test_OnCommand(dwID, dwCmdID, dwParam, pParam)
  window.settitle(dwID, "1234567")
  window.trace(window.gettitle(dwID))
  window.msgbox(1)
  return 1
end

function o()
  CreateGuildWnd()
end

function p()
  local days, s
  window.trace("start12345678")
  window.trace("...")
  for i = 0, 5 do
    window.trace(i)
  end
  days = {
    0,
    0,
    1,
    2,
    1,
    0
  }
  for i, v in ipairs(days) do
    window.trace(i .. " - " .. v)
  end
  window.trace("end")
end

function q()
  window.trace("====================")
end

function Test_OnBiasEditIcon(dwID, dwCmdID, dwParam, pParam)
  window.onedit(dwID)
  window.seticon(window.find(window.parent(dwID), 20040), window.gettitleint(dwID))
  game.testinitvalues()
  return 1
end

function Test_OnBiasScrollIcon(dwID, dwCmdID, dwParam, pParam)
  window.onscroll(dwID, dwParam)
  window.seticon(window.find(window.parent(dwID), 20040), window.gettitleint(window.find(window.parent(dwID), 20003)))
  game.testinitvalues()
  return 1
end

function Test_OnBaseEdit(dwID, dwCmdID, dwParam, pParam)
  window.onedit(dwID)
  game.testbiascolor(window.parent(dwID), 0)
  return 1
end

function Test_OnBaseScroll(dwID, dwCmdID, dwParam, pParam)
  window.onscroll(dwID, dwParam)
  game.testbiascolor(window.parent(dwID), 0)
  return 1
end

function Test_OnMaskEdit(dwID, dwCmdID, dwParam, pParam)
  window.onedit(dwID)
  game.testbiascolor(window.parent(dwID), 12)
  return 1
end

function Test_OnMaskScroll(dwID, dwCmdID, dwParam, pParam)
  window.onscroll(dwID, dwParam)
  game.testbiascolor(window.parent(dwID), 12)
  return 1
end

function Test_OnBaseUpColor(dwID, dwCmdID, dwParam, pParam)
  game.testbiascolor(window.parent(dwID), 0)
  return 1
end

function Test_OnBaseDrawColor(dwID, dwCmdID, dwParam, pParam)
  game.testbasemode(dwID)
  return 1
end

function Test_OnMaskUpColor(dwID, dwCmdID, dwParam, pParam)
  game.testbiascolor(window.parent(dwID), 12)
  return 1
end

function Test_OnMaskDrawColor(dwID, dwCmdID, dwParam, pParam)
  game.testmaskmode(dwID)
  return 1
end

function Test_OnCopyValues(dwID, dwCmdID, dwParam, pParam)
  game.testcopyvalues()
  return 1
end

function OnClickNetID(dwID, dwCmdID, dwParam, pParam)
  local w
  w = GetChatInputWindow()
  window.inputtext(w, window.gettitle(dwID))
  return 1
end
