Wnd_FJJWINDEF_BASE = 0
Wnd_FJJWINDEF_STATIC = 1
Wnd_FJJWINDEF_EDIT = 2
Wnd_FJJWINDEF_BUTTON = 3
Wnd_FJJWINDEF_rev = {}
Wnd_FJJWINDEF_rev[Wnd_FJJWINDEF_BASE] = "BASE"
Wnd_FJJWINDEF_rev[Wnd_FJJWINDEF_STATIC] = "STATIC"
Wnd_FJJWINDEF_rev[Wnd_FJJWINDEF_EDIT] = "EDIT"
Wnd_FJJWINDEF_rev[Wnd_FJJWINDEF_BUTTON] = "BUTTON"
FJJ_windowdef = {}
FJJ_windowdef.prototype = {id = 0, type = 0}
FJJ_windowdef.mt = {}

function FJJ_windowdef.new(o)
  setmetatable(o, FJJ_windowdef.mt)
  FJJ_windowdef.mt.__index = FJJ_windowdef.prototype
  return o
end

FJJ_windowlist = {}
FJJ_windowlistn = 0

function FJJ_AddNewWindow(id, type)
  FJJ_windowlist[FJJ_windowlistn] = FJJ_windowdef.new({})
  FJJ_windowlist[FJJ_windowlistn].child = {}
  FJJ_windowlist[FJJ_windowlistn].childn = 0
  FJJ_windowlist[FJJ_windowlistn].id = id
  FJJ_windowlist[FJJ_windowlistn].type = type
  FJJ_windowlistn = FJJ_windowlistn + 1
  return FJJ_windowlist[FJJ_windowlistn - 1]
end

function FJJ_AddChildWin(win, id, type)
  win.child[win.childn] = {id = 0, type = 0}
  win.child[win.childn].id = id
  win.child[win.childn].type = type
  win.childn = win.childn + 1
end

Wnd_FJJMAINWIN = 0
Wnd_FJJ_movemode = 0

function OnTestButton1(dwID, dwCmdID, dwParam, pParam)
  window.create(387, 0, 0, SYSTEM_HANDLER)
  return 1
end

function FjjMainWinLoad(dwID, dwCmdID, dwParam, pParam)
  Wnd_FJJMAINWIN = dwID
  return 1
end

function OnFjjCreateWin1(dwID, dwCmdID, dwParam, pParam)
  local newwinid = window.create(23010, 0, 0, SYSTEM_HANDLER)
  local newwin_x = window.left(newwinid)
  local newwin_y = window.top(newwinid)
  window.insertitemstr(window.find(Wnd_FJJMAINWIN, 23002), "\181\248\181\161:" .. newwinid, 22001)
  FJJ_AddNewWindow(newwinid, Wnd_FJJWINDEF_BASE)
  return 1
end

function OnFJJSelectObj(dwID, dwCmdID, dwParam, pParam)
  if tonumber(dwParam) >= 0 then
    window.settitle(window.find(Wnd_FJJMAINWIN, 23004), "total:" .. window.getlistitemnum(window.find(Wnd_FJJMAINWIN, 23002)) .. "  windowID:" .. FJJ_windowlist[tonumber(dwParam)].id)
    FjjrefreshChildList()
    FjjUpdateChildData(FjjGetFocusWndId())
  else
  end
  return 1
end

function FjjrefreshChildList()
  local selindex = window.getcheckitem(window.find(Wnd_FJJMAINWIN, 23002))
  if selindex == -1 then
    return 1
  end
  local parentwin = FJJ_windowlist[selindex].id
  local newwin_x = window.left(Wnd_FJJMAINWIN)
  local newwin_y = window.top(Wnd_FJJMAINWIN)
  local mylist = window.find(Wnd_FJJMAINWIN, 23005)
  window.clearlist(mylist)
  for i = 0, FJJ_windowlist[selindex].childn - 1 do
    window.insertitemstr(mylist, Wnd_FJJWINDEF_rev[FJJ_windowlist[selindex].child[i].type] .. ":" .. FJJ_windowlist[selindex].child[i].id, 22001)
  end
end

function OnFjjCreateBtn1(dwID, dwCmdID, dwParam, pParam)
  local selindex = window.getcheckitem(window.find(Wnd_FJJMAINWIN, 23002))
  if selindex == -1 then
    return 1
  end
  local parentwin = FJJ_windowlist[selindex].id
  local newwin_x = window.left(parentwin)
  local newwin_y = window.top(parentwin)
  local newbtnid = window.create(23012, parentwin, 0, SYSTEM_HANDLER)
  window.move(newbtnid, newwin_x + 10, newwin_y + 30)
  FJJ_AddChildWin(FJJ_windowlist[selindex], newbtnid, Wnd_FJJWINDEF_BUTTON)
  FjjrefreshChildList()
  return 1
end

function OnFjjCreateStc1(dwID, dwCmdID, dwParam, pParam)
  local selindex = window.getcheckitem(window.find(Wnd_FJJMAINWIN, 23002))
  if selindex == -1 then
    return 1
  end
  local parentwin = FJJ_windowlist[selindex].id
  local newwin_x = window.left(parentwin)
  local newwin_y = window.top(parentwin)
  local newbtnid = window.create(23011, parentwin, 0, SYSTEM_HANDLER)
  window.move(newbtnid, newwin_x + 10, newwin_y + 30)
  FJJ_AddChildWin(FJJ_windowlist[selindex], newbtnid, Wnd_FJJWINDEF_STATIC)
  FjjrefreshChildList()
  return 1
end

function OnFjjCreateEdt1(dwID, dwCmdID, dwParam, pParam)
  local selindex = window.getcheckitem(window.find(Wnd_FJJMAINWIN, 23002))
  if selindex == -1 then
    return 1
  end
  local parentwin = FJJ_windowlist[selindex].id
  local newwin_x = window.left(parentwin)
  local newwin_y = window.top(parentwin)
  local newbtnid = window.create(23013, parentwin, 0, SYSTEM_HANDLER)
  window.move(newbtnid, newwin_x + 10, newwin_y + 30)
  FJJ_AddChildWin(FJJ_windowlist[selindex], newbtnid, Wnd_FJJWINDEF_EDIT)
  FjjrefreshChildList()
  return 1
end

function FjjUpdateChildData(childid)
  window.settitle(window.find(Wnd_FJJMAINWIN, 23023), window.gettitle(childid))
end

function FjjGetFocusWndId()
  local selindex = window.getcheckitem(window.find(Wnd_FJJMAINWIN, 23002))
  local selchildindex = window.getcheckitem(window.find(Wnd_FJJMAINWIN, 23005))
  if selindex == -1 then
    return 1
  end
  if selchildindex == -1 then
    return FJJ_windowlist[selindex].id
  end
  return FJJ_windowlist[selindex].child[selchildindex].id
end

function OnFJJSelectChildObj(dwID, dwCmdID, dwParam, pParam)
  local selindex = window.getcheckitem(window.find(Wnd_FJJMAINWIN, 23002))
  local selchildindex = window.getcheckitem(window.find(Wnd_FJJMAINWIN, 23005))
  if selindex == -1 then
    return 1
  end
  FjjUpdateChildData(FjjGetFocusWndId())
  return 1
end

function OnFjjMr(dwID, dwCmdID, dwParam, pParam)
  local selindex = window.getcheckitem(window.find(Wnd_FJJMAINWIN, 23002))
  local selchildindex = window.getcheckitem(window.find(Wnd_FJJMAINWIN, 23005))
  if selindex == -1 then
    return 1
  end
  local childid = FjjGetFocusWndId()
  if Wnd_FJJ_movemode == 0 then
    window.move(childid, window.left(childid) + 2, window.top(childid) + 0)
  else
    window.setwindowsize(childid, window.width(childid) + 2, window.height(childid) + 0)
  end
  return 1
end

function OnFjjMl(dwID, dwCmdID, dwParam, pParam)
  local selindex = window.getcheckitem(window.find(Wnd_FJJMAINWIN, 23002))
  local selchildindex = window.getcheckitem(window.find(Wnd_FJJMAINWIN, 23005))
  if selindex == -1 then
    return 1
  end
  local childid = FjjGetFocusWndId()
  if Wnd_FJJ_movemode == 0 then
    window.move(childid, window.left(childid) - 2, window.top(childid) + 0)
  else
    window.setwindowsize(childid, window.width(childid) - 2, window.height(childid) + 0)
  end
  return 1
end

function OnFjjMu(dwID, dwCmdID, dwParam, pParam)
  local selindex = window.getcheckitem(window.find(Wnd_FJJMAINWIN, 23002))
  local selchildindex = window.getcheckitem(window.find(Wnd_FJJMAINWIN, 23005))
  if selindex == -1 then
    return 1
  end
  local childid = FjjGetFocusWndId()
  if Wnd_FJJ_movemode == 0 then
    window.move(childid, window.left(childid) + 0, window.top(childid) - 2)
  else
    window.setwindowsize(childid, window.width(childid) + 0, window.height(childid) - 2)
  end
  return 1
end

function OnFjjMd(dwID, dwCmdID, dwParam, pParam)
  local selindex = window.getcheckitem(window.find(Wnd_FJJMAINWIN, 23002))
  local selchildindex = window.getcheckitem(window.find(Wnd_FJJMAINWIN, 23005))
  if selindex == -1 then
    return 1
  end
  local childid = FjjGetFocusWndId()
  if Wnd_FJJ_movemode == 0 then
    window.move(childid, window.left(childid) + 0, window.top(childid) + 2)
  else
    window.setwindowsize(childid, window.width(childid) + 0, window.height(childid) + 2)
  end
  return 1
end

function OnFjjEditTitle(dwID, dwCmdID, dwParam, pParam)
  local selindex = window.getcheckitem(window.find(Wnd_FJJMAINWIN, 23002))
  local selchildindex = window.getcheckitem(window.find(Wnd_FJJMAINWIN, 23005))
  if selindex == -1 then
    return 1
  end
  local childid = FjjGetFocusWndId()
  window.settitle(childid, window.gettitle(dwID))
  return 1
end

function OnFjjChangeMoveMode0(dwID, dwCmdID, dwParam, pParam)
  Wnd_FJJ_movemode = 0
  return 1
end

function OnFjjChangeMoveMode1(dwID, dwCmdID, dwParam, pParam)
  Wnd_FJJ_movemode = 1
  return 1
end
