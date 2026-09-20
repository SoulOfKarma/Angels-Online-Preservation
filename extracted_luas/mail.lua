MAIL_CUR_PAGE = 0
WndBaseID = 0
WND_COPY = 0
COPY_CUR_PAGE = 0
WND_RECEIVER = 0
RECE_CUR_PAGE = 0

function ChangePage(dwWndBaseID)
  if MAIL_CUR_PAGE == 0 then
    window.show(window.find(dwWndBaseID, 3205), true)
    window.show(window.find(dwWndBaseID, 3206), false)
    window.show(window.find(dwWndBaseID, 3207), false)
  elseif MAIL_CUR_PAGE == 1 then
    window.show(window.find(dwWndBaseID, 3205), false)
    window.show(window.find(dwWndBaseID, 3206), true)
    window.show(window.find(dwWndBaseID, 3207), false)
  elseif MAIL_CUR_PAGE == 2 then
    window.show(window.find(dwWndBaseID, 3205), false)
    window.show(window.find(dwWndBaseID, 3206), false)
    window.show(window.find(dwWndBaseID, 3207), true)
  end
  return 1
end

function OnMailCommand(dwID, dwCmdID, dwParam, pParam)
  local appdata = window.getappdata(dwID)
  game.mailcommand(0, appdata, 0, 0)
  return 1
end

function OnDelMailConfirm(dwID, dwCmdID, dwParam, pParam)
  local appdata = window.getappdata(dwID)
  game.mailcommand(0, appdata, 0, 0)
  return 1
end

function OnDelMail_Ok(dwID, dwCmdID, dwParam, pParam)
  local appdata = window.getappdata(dwID)
  game.mailcommand(0, appdata, 0, 0)
  local DelConfirm = window.parent(dwID)
  window.destroy(DelConfirm)
  return 1
end

function OnDelMail_Cancel(dwID, dwCmdID, dwParam, pParam)
  local DelConfirm = window.parent(dwID)
  window.destroy(DelConfirm)
  return 1
end

function OnAddMibConfirm(dwID, dwCmdID, dwParam, pParam)
  local appdata = window.getappdata(dwID)
  game.mailcommand(0, appdata, 0, 0)
  return 1
end

function OnAddMib_Ok(dwID, dwCmdID, dwParam, pParam)
  local appdata = window.getappdata(dwID)
  game.mailcommand(0, appdata, 0, 0)
  local AddMibConfirm = window.parent(dwID)
  window.destroy(AddMibConfirm)
  return 1
end

function OnAddMib_Cancel(dwID, dwCmdID, dwParam, pParam)
  local AddMibConfirm = window.parent(dwID)
  window.destroy(AddMibConfirm)
  return 1
end

function OnReceivePage(dwID, dwCmdID, dwParam, pParam)
  MAIL_CUR_PAGE = 0
  WndBaseID = window.parent(window.parent(dwID))
  ChangePage(WndBaseID)
  local appdata = window.getappdata(dwID)
  game.mailcommand(0, appdata, 0, 0)
  return 1
end

function OnWritePage(dwID, dwCmdID, dwParam, pParam)
  MAIL_CUR_PAGE = 1
  WndBaseID = window.parent(window.parent(dwID))
  ChangePage(WndBaseID)
  local appdata = window.getappdata(dwID)
  game.mailcommand(0, appdata, 0, 0)
  local WordMEdit = window.find(WndBaseID, 3241)
  window.setmaxline(WordMEdit, 16)
  return 1
end

function OnBackupPage(dwID, dwCmdID, dwParam, pParam)
  MAIL_CUR_PAGE = 2
  WndBaseID = window.parent(window.parent(dwID))
  ChangePage(WndBaseID)
  local appdata = window.getappdata(dwID)
  game.mailcommand(0, appdata, 0, 0)
  return 1
end

function OnSortMailList(dwID, dwCmdID, dwParam, pParam)
  local appdata = window.getappdata(dwID)
  game.mailcommand(0, appdata, 0, 0)
  return 1
end

function OnCreateCopyWnd(dwID, dwCmdID, dwParam, pParam)
  if window.isexist(WND_COPY) then
    return 1
  end
  WND_COPY = window.create(3301, window.parent(dwID), 0, 0)
  local WndReceive = window.parent(dwID)
  local PosX = window.left(WndReceive) + 2
  local PosY = window.top(WndReceive) + 60
  window.move(WND_COPY, PosX, PosY)
  local appdata = window.getappdata(dwID)
  game.mailcommand(0, appdata, 0, 0)
  return 1
end

function OnChangeCopyPage(dwID, dwCmdID, dwParam, pParam)
  local Appdata = window.getappdata(dwID)
  local WndCopy = window.parent(dwID)
  if Appdata == 3309 then
    window.show(window.find(WndCopy, 3305), true)
    window.show(window.find(WndCopy, 3307), false)
    window.seticon(window.find(WndCopy, 3309), 3085)
    window.seticon(window.find(WndCopy, 3310), 3084)
    COPY_CUR_PAGE = 0
  elseif Appdata == 3310 then
    window.show(window.find(WndCopy, 3305), false)
    window.show(window.find(WndCopy, 3307), true)
    window.seticon(window.find(WndCopy, 3309), 3084)
    window.seticon(window.find(WndCopy, 3310), 3085)
    COPY_CUR_PAGE = 1
  end
  return 1
end

function OnCpoy_OK(dwID, dwCmdID, dwParam, pParam)
  local appdata = window.getappdata(dwID)
  game.mailcommand(0, appdata, 0, 0)
  window.destroy(window.parent(dwID))
  WND_COPY = 0
  return 1
end

function OnCpoy_Cancel(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  WND_COPY = 0
  return 1
end

function OnCreateReceWnd(dwID, dwCmdID, dwParam, pParam)
  if window.isexist(WND_RECEIVER) then
    return 1
  end
  WND_RECEIVER = window.create(3331, window.parent(dwID), 0, 0)
  local WndReceive = window.parent(dwID)
  local PosX = window.left(WndReceive) + 2
  local PosY = window.top(WndReceive) + 60
  window.move(WND_RECEIVER, PosX, PosY)
  local appdata = window.getappdata(dwID)
  game.mailcommand(0, appdata, 0, 0)
  return 1
end

function OnChangeRecePage(dwID, dwCmdID, dwParam, pParam)
  local Appdata = window.getappdata(dwID)
  local WndRece = window.parent(dwID)
  if Appdata == 3339 then
    window.show(window.find(WndRece, 3335), true)
    window.show(window.find(WndRece, 3337), false)
    window.seticon(window.find(WndRece, 3339), 3085)
    window.seticon(window.find(WndRece, 3340), 3084)
    RECE_CUR_PAGE = 0
  elseif Appdata == 3340 then
    window.show(window.find(WndRece, 3335), false)
    window.show(window.find(WndRece, 3337), true)
    window.seticon(window.find(WndRece, 3339), 3084)
    window.seticon(window.find(WndRece, 3340), 3085)
    RECE_CUR_PAGE = 1
  end
  return 1
end

function OnRece_OK(dwID, dwCmdID, dwParam, pParam)
  local appdata = window.getappdata(dwID)
  game.mailcommand(0, appdata, 0, 0)
  window.destroy(window.parent(dwID))
  WND_RECEIVER = 0
  return 1
end

function OnRece_Cancel(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  WND_RECEIVER = 0
  return 1
end

function OnClickUnreadMail(dwID, dwCmdID, dwParam, pParam)
  if window.isexist(WND_FRIEND) == false then
    CreateFriendWnd()
  end
  window.setcheck(window.find(WND_FRIEND, 2319), false)
  window.setcheck(window.find(WND_FRIEND, 2320), false)
  window.setcheck(window.find(WND_FRIEND, 2321), true)
  window.setcheck(window.find(WND_FRIEND, 1200), false)
  window.setcheck(window.find(WND_FRIEND, 12230), false)
  window.show(window.find(WND_FRIEND, 2302), false)
  window.show(window.find(WND_FRIEND, 2303), false)
  window.show(window.find(WND_FRIEND, 3201), true)
  window.show(window.find(WND_FRIEND, 1202), false)
  window.show(window.find(WND_FRIEND, 12232), false)
  MAIL_CUR_PAGE = 0
  window.show(window.find(WND_FRIEND, 3205), true)
  window.show(window.find(WND_FRIEND, 3206), false)
  window.show(window.find(WND_FRIEND, 3207), false)
  game.mailcommand(0, 2321, 0, 0)
  window.destroy(window.parent(dwID))
  return 1
end

function OnSelectMail(dwID, dwCmdID, dwParam, pParam)
  local appdata = window.getappdata(dwID)
  game.mailcommand(0, appdata, dwParam, 0)
  return 1
end

function OnShowListTooltip(dwID, dwCmdID, dwParam, pParam)
  game.showlisttooltip(dwParam, pParam)
  return 1
end

function OnTestMail(dwID, dwCmdID, dwParam, pParam)
  local MailList = window.find(window.parent(dwID), 3214)
  window.insertitemstr(MailList, "aaa", 0)
  window.setsubitemstr(MailList, 0, 0, "test2", 0)
  window.setsubitemstr(MailList, 0, 1, "05/10", 0)
  return 1
end
