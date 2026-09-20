function Setting_ChangePage(dwID, dwCmdID, dwParam, pParam)
  local Wnd = window.parent(dwID)
  
  local appdata = window.getappdata(dwID)
  local page = window.find(Wnd, 12011)
  if page ~= 0 then
    window.show(page, false)
  end
  page = window.find(Wnd, 12031)
  if page ~= 0 then
    window.show(page, false)
  end
  page = window.find(Wnd, 12081)
  if page ~= 0 then
    window.show(page, false)
  end
  page = window.find(Wnd, appdata)
  window.show(page, true)
  return 1
end

function Open_Setting(dwID, dwCmdID, dwParam, pParam)
  local Wnd = window.create(12002, 0, 0, 0)
  local wnd_hd = window.find(Wnd, 12003)
  window.setradio(wnd_hd, 0)
  for n = 12018, 12020 do
    wnd_hd = window.find(Wnd, n)
    if wnd_hd ~= 0 then
      window.setrange(wnd_hd, 0, 10)
    end
  end
  wnd_hd = window.find(Wnd, 12044)
  window.setradio(wnd_hd, 0)
  wnd_hd = window.find(Wnd, 12046)
  window.setradio(wnd_hd, 0)
  wnd_hd = window.find(Wnd, 12048)
  window.setradio(wnd_hd, 0)
  wnd_hd = window.find(Wnd, 12055)
  window.setradio(wnd_hd, 0)
  wnd_hd = window.find(Wnd, 12063)
  window.setradio(wnd_hd, 0)
  wnd_hd = window.find(Wnd, 12090)
  window.setradio(wnd_hd, 0)
  wnd_hd = window.find(Wnd, 12096)
  window.setradio(wnd_hd, 0)
  wnd_hd = window.find(Wnd, 12108)
  window.setradio(wnd_hd, 1)
  local page = window.find(Wnd, 12031)
  if page ~= 0 then
    window.show(page, false)
  end
  page = window.find(Wnd, 12081)
  if page ~= 0 then
    window.show(page, false)
  end
  return 1
end

function Open_ListDown(dwID, dwCmdID, dwParam, pParam)
  local Wnd = window.parent(dwID)
  local Wnd_hd = window.create(12035, Wnd, 0, 0)
  if Wnd_hd ~= nil then
    window.insertitemstr(Wnd_hd, " 640 X 480", 0)
    window.insertitemstr(Wnd_hd, " 800 X 600", 0)
    window.insertitemstr(Wnd_hd, " 1024 X 768", 0)
  end
  return 1
end
