WND_SKILLS = 0
WND_SKILLS_X = -1
WND_SKILLS_Y = -1
WND_SKILLS_SELECT = 0
WND_SKILLS_TYPE = 1
WND_SKILLS_PAGE = 1
WND_SKILLS_CHANGE = 0
WND_SKILLS_CHANGE_X = -1
WND_SKILLS_CHANGE_Y = -1
WND_OLD_SKILLS_SELECT = 0
WND_NEW_SKILLS_SELECT = 0
WND_NEW_SKILLS_TYPE = 1

function CreateSkillsWnd()
  local w, i
  if window.isexist(WND_SKILLS) then
    if window.isvisible(WND_SKILLS) then
      window.show(WND_SKILLS, false)
    else
      window.show(WND_SKILLS, true)
      window.setforeground(WND_SKILLS)
    end
    return
  end
  WND_SKILLS = window.create(12130, 0, 0, SYSTEM_HANDLER)
  if 0 > WND_SKILLS_X or 0 > WND_SKILLS_Y then
    window.move(WND_SKILLS, SYSTEM_SCREEN_WIDTH / 2, SYSTEM_SCREEN_HEIGHT / 2 - 200)
  else
    window.move(WND_SKILLS, WND_SKILLS_X, WND_SKILLS_Y)
  end
  window.regsetting(WND_SKILLS, "WND_SKILLS")
  window.show(window.find(WND_SKILLS, 12133), true)
  window.show(window.find(WND_SKILLS, 12134), false)
  w = window.find(WND_SKILLS, 12131)
  window.setradio(w, 0)
  w = window.find(WND_SKILLS, 12148)
  window.setradio(w, 0)
  WND_SKILLS_PAGE = 1
  WND_SKILLS_TYPE = 1
  game.initskillswnd(window.find(WND_SKILLS, 12133), WND_SKILLS_SELECT)
  game.initownskills(window.find(WND_SKILLS, 12134), WND_SKILLS_SELECT, WND_SKILLS_TYPE)
end

function OnChangeSkillPage(dwID, dwCmdID, dwParam, pParam)
  WND_SKILLS_PAGE = 1
  WND_SKILLS_SELECT = 0
  if dwCmdID == 12131 then
    window.show(window.find(window.parent(dwID), 12133), true)
    window.show(window.find(window.parent(dwID), 12134), false)
  elseif dwCmdID == 12132 then
    window.show(window.find(window.parent(dwID), 12133), false)
    window.show(window.find(window.parent(dwID), 12134), true)
  end
  game.initskillswnd(window.find(WND_SKILLS, 12133), WND_SKILLS_SELECT)
  game.initownskills(window.find(WND_SKILLS, 12134), WND_SKILLS_SELECT, WND_SKILLS_TYPE)
  return 1
end

function OnChangeSkills(dwID, dwCmdID, dwParam, pParam)
  local w, par, i, res1, res2
  if game.isdef("__PEAK_LV_SYSTEM") == true then
    res1 = 27681
    res2 = 27689
  else
    res1 = 12135
    res2 = 12140
  end
  par = window.parent(dwID)
  for i = res1, res2 do
    w = window.find(par, i)
    if dwCmdID == i then
      window.modifyiconattrib(w, 0, ICON_ATTRIB_GRAY)
    else
      window.modifyiconattrib(w, ICON_ATTRIB_GRAY, 0)
    end
  end
  WND_SKILLS_SELECT = dwCmdID - res1
  WND_SKILLS_PAGE = 1
  game.initskillswnd(window.find(WND_SKILLS, 12133), WND_SKILLS_SELECT)
  return 1
end

function OnChangeUneqType(dwID, dwCmdID, dwParam, pParam)
  WND_SKILLS_TYPE = dwCmdID - 12148 + 1
  WND_SKILLS_SELECT = 0
  WND_SKILLS_PAGE = 1
  game.initownskills(window.find(WND_SKILLS, 12134), WND_SKILLS_SELECT, WND_SKILLS_TYPE)
  return 1
end

function OnChangeUneqSkills(dwID, dwCmdID, dwParam, pParam)
  local w, par, i
  par = window.parent(dwID)
  for i = 12153, 12164 do
    w = window.find(par, i)
    if dwCmdID == i then
      window.modifyiconattrib(w, 0, ICON_ATTRIB_GRAY)
    else
      window.modifyiconattrib(w, ICON_ATTRIB_GRAY, 0)
    end
  end
  WND_SKILLS_SELECT = dwCmdID - 12153
  WND_SKILLS_PAGE = 1
  game.initownskills(window.find(WND_SKILLS, 12134), WND_SKILLS_SELECT, WND_SKILLS_TYPE)
  return 1
end

function OnChangeMagicPage(dwID, dwCmdID, dwParam, pParam)
  if dwCmdID == 12146 and WND_SKILLS_PAGE > 1 then
    WND_SKILLS_PAGE = WND_SKILLS_PAGE - 1
    game.initskillswnd(window.find(WND_SKILLS, 12133), WND_SKILLS_SELECT)
  elseif dwCmdID == 12147 then
    WND_SKILLS_PAGE = WND_SKILLS_PAGE + 1
    game.initskillswnd(window.find(WND_SKILLS, 12133), WND_SKILLS_SELECT)
  elseif dwCmdID == 12170 and WND_SKILLS_PAGE > 1 then
    WND_SKILLS_PAGE = WND_SKILLS_PAGE - 1
    game.initownskills(window.find(WND_SKILLS, 12134), WND_SKILLS_SELECT, WND_SKILLS_TYPE)
  elseif dwCmdID == 12171 then
    WND_SKILLS_PAGE = WND_SKILLS_PAGE + 1
    game.initownskills(window.find(WND_SKILLS, 12134), WND_SKILLS_SELECT, WND_SKILLS_TYPE)
  end
  return 1
end

function OnDragSkillMagics(dwID, dwCmdID, dwParam, pParam)
  game.dragmagics(dwID, dwCmdID, dwParam, pParam)
  return 1
end

function OnChangeUneqChangeType(dwID, dwCmdID, dwParam, pParam)
  WND_NEW_SKILLS_TYPE = dwCmdID - 12194 + 1
  WND_NEW_SKILLS_SELECT = 0
  game.initchangeskills(window.find(WND_SKILLS_CHANGE, 12181), WND_OLD_SKILLS_SELECT, WND_NEW_SKILLS_SELECT, WND_NEW_SKILLS_TYPE)
  return 1
end

function OnChooseOldSkills(dwID, dwCmdID, dwParam, pParam)
  local w, par, i, res1, res2
  if game.isdef("__PEAK_LV_SYSTEM") == true then
    res1 = 27672
    res2 = 27680
  else
    res1 = 12188
    res2 = 12193
  end
  par = window.parent(dwID)
  for i = res1, res2 do
    w = window.find(par, i)
    if dwCmdID == i then
      window.modifyiconattrib(w, 0, ICON_ATTRIB_GRAY)
    else
      window.modifyiconattrib(w, ICON_ATTRIB_GRAY, 0)
    end
  end
  WND_OLD_SKILLS_SELECT = dwCmdID - res1
  game.initchangeskills(window.find(WND_SKILLS_CHANGE, 12181), WND_OLD_SKILLS_SELECT, WND_NEW_SKILLS_SELECT, WND_NEW_SKILLS_TYPE)
  return 1
end

function OnChooseNewSkills(dwID, dwCmdID, dwParam, pParam)
  local w, par, i
  par = window.parent(dwID)
  for i = 12203, 12214 do
    w = window.find(par, i)
    if dwCmdID == i then
      window.modifyiconattrib(w, 0, ICON_ATTRIB_GRAY)
    else
      window.modifyiconattrib(w, ICON_ATTRIB_GRAY, 0)
    end
  end
  WND_NEW_SKILLS_SELECT = dwCmdID - 12203
  game.initchangeskills(window.find(WND_SKILLS_CHANGE, 12181), WND_OLD_SKILLS_SELECT, WND_NEW_SKILLS_SELECT, WND_NEW_SKILLS_TYPE)
  return 1
end

function PopChangeSkillsAsking(dwID, dwCmdID, dwParam, pParam)
  local wnd = window.create(12217, window.parent(dwID), 0, 0)
  game.setchangeskillcostitem(window.find(wnd, 12218))
  return 1
end

function OnChangeSkillsOk(dwID, dwCmdID, dwParam, pParam)
  local w, p, s1, s2
  p = window.parent(window.parent(dwID))
  if game.isdef("__PEAK_LV_SYSTEM") == true then
    w = window.find(p, 27672 + WND_OLD_SKILLS_SELECT)
  else
    w = window.find(p, 12188 + WND_OLD_SKILLS_SELECT)
  end
  s1 = window.getappdata(w)
  w = window.find(p, 12203 + WND_NEW_SKILLS_SELECT)
  s2 = window.getappdata(w)
  game.netcommand2(10, s1, s2)
  p = window.parent(p)
  window.destroy(p)
  return 1
end

function OnCancelChangeSkills(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(window.parent(dwID)))
  return 1
end

function OnCloseSkillWnd(dwID, dwCmdID, dwParam, pParam)
  window.destroy(WND_SKILLS)
  WND_SKILLS = 0
  return 1
end

function OnUseSkillsMagic(dwID, dwCmdID, dwParam, pParam)
  game.useskillsmagic(dwID, dwCmdID, dwParam, pParam)
  return 1
end

function OnDragSkillMagic(dwID, dwCmdID, dwParam, pParam)
  game.dragmagic(dwID, dwCmdID, dwParam, pParam)
  return 1
end
