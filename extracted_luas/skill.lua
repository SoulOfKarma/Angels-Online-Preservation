WND_SKILL = 0
WND_SKILL_X = -1
WND_SKILL_Y = -1
WND_SKILL_SELECT = 0

function CreateSkillWnd()
  local w, i
  if window.isexist(WND_SKILL) then
    if window.isvisible(WND_SKILL) then
      window.show(WND_SKILL, false)
    else
      window.show(WND_SKILL, true)
    end
    return
  end
  WND_SKILL = window.create(460, 0, 0, SYSTEM_HANDLER)
  if 0 > WND_SKILL_X or 0 > WND_SKILL_Y then
    window.move(WND_SKILL, SYSTEM_SCREEN_WIDTH / 2, SYSTEM_SCREEN_HEIGHT / 2 - 200)
  else
    window.move(WND_SKILL, WND_SKILL_X, WND_SKILL_Y)
  end
  window.regsetting(WND_SKILL, "WND_SKILL")
  w = window.find(WND_SKILL, 461)
  window.setradio(w, 0)
  game.initskillwnd(window.find(WND_SKILL, 465), WND_SKILL_SELECT)
  game.initownskill(window.find(WND_SKILL, 467))
end

function OnChangeSkillTab(dwID, dwCmdID, dwParam, pParam)
  if dwCmdID == 461 then
    window.show(window.find(window.parent(dwID), 465), true)
    window.show(window.find(window.parent(dwID), 467), false)
  elseif dwCmdID == 462 then
    window.show(window.find(window.parent(dwID), 465), false)
    window.show(window.find(window.parent(dwID), 467), true)
  end
  return 1
end

function OnChangeSkill(dwID, dwCmdID, dwParam, pParam)
  local w, par, i
  par = window.parent(dwID)
  for i = 468, 473 do
    w = window.find(par, i)
    if dwCmdID == i then
      window.modifyiconattrib(w, 0, ICON_ATTRIB_GRAY)
    else
      window.modifyiconattrib(w, ICON_ATTRIB_GRAY, 0)
    end
  end
  WND_SKILL_SELECT = dwCmdID - 468
  game.initskillwnd(window.find(WND_SKILL, 465), WND_SKILL_SELECT)
  return 1
end

function OnDragSkillMagic(dwID, dwCmdID, dwParam, pParam)
  game.dragmagic(dwID, dwCmdID, dwParam, pParam)
  return 1
end

function OnSkillStep1Next(dwID, dwCmdID, dwParam, pParam)
  local w, p
  p = window.parent(dwID)
  window.show(p, false)
  p = window.parent(p)
  w = window.find(p, 492)
  window.show(w, true)
  game.initchangeskillstep2(p)
  return 1
end

function OnSkillStep2Next(dwID, dwCmdID, dwParam, pParam)
  local w, p
  p = window.parent(dwID)
  window.show(p, false)
  p = window.parent(p)
  w = window.find(p, 493)
  window.show(w, true)
  game.initchangeskillstep3(p)
  return 1
end

function OnSkillStep2Prev(dwID, dwCmdID, dwParam, pParam)
  local w, p
  p = window.parent(dwID)
  window.show(p, false)
  p = window.parent(p)
  w = window.find(p, 491)
  window.show(w, true)
  return 1
end

function OnSkillStep3Ok(dwID, dwCmdID, dwParam, pParam)
  local w, p, s1, s2
  p = window.parent(dwID)
  w = window.find(p, 507)
  s1 = window.getappdata(w)
  w = window.find(p, 508)
  s2 = window.getappdata(w)
  game.netcommand2(10, s1, s2)
  p = window.parent(p)
  window.destroy(p)
  return 1
end

function OnSkillStep3Cancel(dwID, dwCmdID, dwParam, pParam)
  local p
  p = window.parent(dwID)
  p = window.parent(p)
  window.destroy(p)
  return 1
end

function OnChangeClassSkill(dwID, dwCmdID, dwParam, pParam)
  if dwCmdID == 526 then
    window.show(window.find(window.parent(dwID), 528), true)
    window.show(window.find(window.parent(dwID), 535), false)
  elseif dwCmdID == 527 then
    window.show(window.find(window.parent(dwID), 528), false)
    window.show(window.find(window.parent(dwID), 535), true)
  end
  return 1
end
