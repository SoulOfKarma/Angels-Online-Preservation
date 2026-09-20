WND_SAFEVERIFY = 0
WND_SAFECHANGE = 0
WND_SAFECHANGE2 = 0
WND_SAFEDELETE = 0

function CreateSafeVerifyWnd()
  WND_SAFEVERIFY = window.create(23900, 0, 0, SYSTEM_HANDLER)
  for i = 0, 9 do
    picwnd = window.find(WND_SAFEVERIFY, 23901 + i)
    game.setsafeverifypic(picwnd, i)
  end
end

function OnSafeVerifyChoose(dwID, dwCmdID, dwParam, pParam)
  local passresult = window.find(window.parent(dwID), 23913)
  local nth = window.getappdata(dwID)
  window.settitle(passresult, window.gettitle(passresult) .. nth)
  return 1
end

function OnSafeVerifyOK(dwID, dwCmdID, dwParam, pParam)
  local passresult = window.find(window.parent(dwID), 23913)
  if window.gettitle(passresult) ~= "" then
    rr = game.sendsafeverify(passresult)
    if rr == 0 then
      window.destroy(window.parent(dwID))
    else
      game.addsystemmessage(rr)
    end
  else
    game.addsystemmessage(897)
  end
  return 1
end

function OnSafeVerifyCancel(dwID, dwCmdID, dwParam, pParam)
  game.safeverifycancel()
  window.destroy(window.parent(dwID))
  return 1
end

function CreateSafeVerifyChangeWnd()
  if window.isexist(WND_SAFECHANGE) then
    return 1
  end
  WND_SAFECHANGE = window.create(24000, 0, 0, SYSTEM_HANDLER)
  for i = 0, 9 do
    picwnd = window.find(WND_SAFECHANGE, 24003 + i)
    game.setsafeverifypic(picwnd, i)
  end
  for i = 0, 9 do
    picwnd = window.find(WND_SAFECHANGE, 24015 + i)
    game.setsafeverifypic(picwnd, i)
  end
  for i = 0, 9 do
    picwnd = window.find(WND_SAFECHANGE, 24027 + i)
    game.setsafeverifypic(picwnd, i)
  end
end

function CreateSafeVerifyChangeWnd2()
  if window.isexist(WND_SAFECHANGE2) then
    return 1
  end
  WND_SAFECHANGE2 = window.create(23999, 0, 0, SYSTEM_HANDLER)
  for i = 0, 9 do
    picwnd = window.find(WND_SAFECHANGE2, 23985 + i)
    game.setsafeverifypic(picwnd, i)
  end
  for i = 0, 9 do
    picwnd = window.find(WND_SAFECHANGE2, 23973 + i)
    game.setsafeverifypic(picwnd, i)
  end
end

function OnSafeVerifyChooseC1(dwID, dwCmdID, dwParam, pParam)
  local passresult = window.find(window.parent(dwID), 24013)
  local nth = window.getappdata(dwID)
  window.settitle(passresult, window.gettitle(passresult) .. nth)
  return 1
end

function OnSafeVerifyChooseC2(dwID, dwCmdID, dwParam, pParam)
  local passresult = window.find(window.parent(dwID), 24025)
  local nth = window.getappdata(dwID)
  window.settitle(passresult, window.gettitle(passresult) .. nth)
  return 1
end

function OnSafeVerifyChooseC3(dwID, dwCmdID, dwParam, pParam)
  local passresult = window.find(window.parent(dwID), 24037)
  local nth = window.getappdata(dwID)
  window.settitle(passresult, window.gettitle(passresult) .. nth)
  return 1
end

function OnSafeVerifyChooseC22(dwID, dwCmdID, dwParam, pParam)
  local passresult = window.find(window.parent(dwID), 23984)
  local nth = window.getappdata(dwID)
  window.settitle(passresult, window.gettitle(passresult) .. nth)
  return 1
end

function OnSafeVerifyChooseC23(dwID, dwCmdID, dwParam, pParam)
  local passresult = window.find(window.parent(dwID), 23972)
  local nth = window.getappdata(dwID)
  window.settitle(passresult, window.gettitle(passresult) .. nth)
  return 1
end

function OnSafeVerifyChooseChangeOK(dwID, dwCmdID, dwParam, pParam)
  passresult1 = window.find(window.parent(dwID), 24013)
  passresult2 = window.find(window.parent(dwID), 24025)
  passresult3 = window.find(window.parent(dwID), 24037)
  if window.gettitle(passresult1) ~= "" then
    if window.gettitle(passresult2) ~= "" then
      if window.gettitle(passresult3) ~= "" then
        if window.gettitle(passresult2) == window.gettitle(passresult3) then
          rr = game.sendsafeverifychange(passresult1, passresult2, passresult3)
          if rr == 0 then
            window.destroy(window.parent(dwID))
          else
            game.addsystemmessage(rr)
          end
        else
          game.addsystemmessage(884)
          window.settitle(passresult2, "")
          window.settitle(passresult3, "")
        end
      else
        game.addsystemmessage(893)
      end
    else
      game.addsystemmessage(892)
    end
  else
    game.addsystemmessage(894)
  end
  return 1
end

function OnSafeVerifyChooseChangeOK2(dwID, dwCmdID, dwParam, pParam)
  passresult1 = window.find(window.parent(dwID), 23998)
  passresult2 = window.find(window.parent(dwID), 23984)
  passresult3 = window.find(window.parent(dwID), 23972)
  if window.gettitle(passresult1) ~= "" then
    if window.gettitle(passresult2) ~= "" then
      if window.gettitle(passresult3) ~= "" then
        if window.gettitle(passresult2) == window.gettitle(passresult3) then
          rr = game.sendsafeverifychange(passresult1, passresult2, passresult3)
          if rr == 0 then
            window.destroy(window.parent(dwID))
          else
            game.addsystemmessage(rr)
          end
        else
          game.addsystemmessage(884)
          window.settitle(passresult2, "")
          window.settitle(passresult3, "")
        end
      else
        game.addsystemmessage(893)
      end
    else
      game.addsystemmessage(892)
    end
  else
    game.addsystemmessage(891)
  end
  return 1
end

function OnSafeVerifySendCancel(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  return 1
end

function CreateSafeVerifyDeleteWnd()
  if window.isexist(WND_SAFEDELETE) then
    return 1
  end
  WND_SAFEDELETE = window.create(24100, 0, 0, SYSTEM_HANDLER)
  for i = 0, 9 do
    picwnd = window.find(WND_SAFEDELETE, 24105 + i)
    game.setsafeverifypic(picwnd, i)
  end
end

function OnSafeVerifyChooseD1(dwID, dwCmdID, dwParam, pParam)
  local passresult = window.find(window.parent(dwID), 24115)
  local nth = window.getappdata(dwID)
  window.settitle(passresult, window.gettitle(passresult) .. nth)
  return 1
end

function OnSafeVerifyDeleteOK(dwID, dwCmdID, dwParam, pParam)
  passresult1 = window.find(window.parent(dwID), 24115)
  if window.gettitle(passresult1) ~= "" then
    rr = game.sendsafeverifydelete(passresult1)
    if rr == 0 then
      window.destroy(window.parent(dwID))
    else
      game.addsystemmessage(rr)
    end
  else
    game.addsystemmessage(894)
  end
  return 1
end

function OnSafeVerifyDeleteCancel(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  return 1
end

function OnSafeVerifyFirstSetOK(dwID, dwCmdID, dwParam, pParam)
  CreateSafeVerifyChangeWnd2()
  window.destroy(window.parent(dwID))
  return 1
end

function OnSafeVerifyFirstSetCancel(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  return 1
end

function OnSafeVerifyReset1(dwID, dwCmdID, dwParam, pParam)
  local passresult = window.find(window.parent(dwID), 23913)
  window.settitle(passresult, "")
  return 1
end

function OnSafeVerifyReset2(dwID, dwCmdID, dwParam, pParam)
  local passresult = window.find(window.parent(dwID), 23998)
  window.settitle(passresult, "")
  passresult = window.find(window.parent(dwID), 23984)
  window.settitle(passresult, "")
  passresult = window.find(window.parent(dwID), 23972)
  window.settitle(passresult, "")
  return 1
end

function OnSafeVerifyReset3(dwID, dwCmdID, dwParam, pParam)
  local passresult = window.find(window.parent(dwID), 24013)
  window.settitle(passresult, "")
  passresult = window.find(window.parent(dwID), 24025)
  window.settitle(passresult, "")
  passresult = window.find(window.parent(dwID), 24037)
  window.settitle(passresult, "")
  return 1
end

function OnSafeVerifyReset4(dwID, dwCmdID, dwParam, pParam)
  local passresult = window.find(window.parent(dwID), 24115)
  window.settitle(passresult, "")
  return 1
end

function OnSafeVerifyButtonMoveIn(dwID, dwCmdID, dwParam, pParam)
  local x, y
  x = window.left(dwID)
  y = window.top(dwID)
  window.show(window.find(window.parent(dwID), 23899), true)
  window.move(window.find(window.parent(dwID), 23899), x, y)
  return 1
end
