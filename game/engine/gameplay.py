from __future__ import annotations

from game.model.board import Position
from game.model.constants import GameState, UnitType
from game.model.skill import SKILLS
from game.model.unit import Unit


class GameplayResolutionMixin:
    """공격, 스킬, 밀치기 같은 전투 해상도 로직만 분리한 믹스인."""

    def _resolve_basic_attack(self, attacker: Unit, target: Unit) -> None:
        """기본 공격 피해, 처치 후 전진, 승리 체크까지 한 번에 처리한다."""
        target_tile = target.position
        self.add_effect("attack_line", target.position, duration=0.22, origin=attacker.position)
        self.add_effect("slash", target.position, duration=0.30)
        damage = attacker.attack(target)
        self.queue_sound("attack")
        self._show_damage_feedback(target, damage, source=attacker.position, heavy=attacker.is_melee())
        if damage > 0:
            self.log(f"{attacker.name} 공격: {target.name}에게 피해 {damage}")
            self.last_feedback = f"{target.name} 체력: {target.hp}/{target.max_hp}"
        else:
            self.log(f"{attacker.name} 공격: {target.name}의 보호막에 막혔습니다.")
            self.last_feedback = "보호막이 피해를 막아냈습니다."
        self._cleanup_dead_units()
        if attacker.is_melee() and not target.is_alive():
            attacker.move(target_tile)
            self.inspected_unit_id = attacker.id
            self.add_effect("move", target_tile, duration=0.32)
            self.log(f"{attacker.name} 전진: 처치 후 빈 칸을 점령했습니다.")
        self._check_victory()
        if self.state == GameState.GAME_OVER:
            self.queue_sound("win")

    def _resolve_skill(self, unit: Unit, target_tile: Position) -> None:
        """유닛 타입에 맞는 스킬 해상도 함수를 호출하고 후처리를 담당한다."""
        unit.use_skill()
        skill = SKILLS[unit.unit_type]
        self.add_effect("skill_cast", unit.position, duration=0.35)
        self.queue_sound("skill")
        if unit.unit_type == UnitType.KING:
            if unit.boss:
                unit.cooldowns["skill"] = max(unit.cooldowns.get("skill", 0), 3)
                teleported, hits = self._resolve_terror_slam(unit, target_tile)
                self.log(f"{unit.name} 스킬 사용: 공포 강림, 피해 대상 {hits}")
                self.last_feedback = "괴물 왕이 순간이동 후 공포 강림을 쏟아냈습니다." if teleported else f"괴물 왕의 공포 강림이 {hits}명을 휩쓸었습니다."
                self._cleanup_dead_units()
                self._check_victory()
                if self.state == GameState.GAME_OVER:
                    self.queue_sound("win")
                return
            target = self.unit_at(target_tile)
            if target is not None and target.team == unit.team:
                target.shield_turns = max(target.shield_turns, 1)
                self.add_effect("shield", target.position, duration=0.70)
                self.add_effect("text", target.position, duration=0.75, text="보호", color=(255, 226, 110))
                self.log(f"{unit.name} 스킬 사용: {skill.name}")
                self.last_feedback = f"{target.name}에게 1턴 보호막을 부여했습니다."
        elif unit.unit_type == UnitType.SWORDMAN:
            self._resolve_charge(unit, target_tile)
        elif unit.unit_type == UnitType.ARCHER:
            hits = self._resolve_piercing_shot(unit, target_tile)
            self.log(f"{unit.name} 스킬 사용: {skill.name}, 피해 대상 {hits}")
            self.last_feedback = f"관통 사격 적중 수: {hits}"
        elif unit.unit_type == UnitType.MAGE:
            hits = self._resolve_flame_burst(unit, target_tile)
            self.log(f"{unit.name} 스킬 사용: {skill.name}, 피해 대상 {hits}")
            self.last_feedback = f"화염 폭발 적중 수: {hits}"
        elif unit.unit_type == UnitType.KNIGHT:
            self._resolve_leap_strike(unit, target_tile)
        elif unit.unit_type == UnitType.BISHOP:
            hits = self._resolve_bishop_beam(unit, target_tile)
            self.log(f"{unit.name} 스킬 사용: {skill.name}, 피해 대상 {hits}")
            self.last_feedback = f"대각 광선 적중 수: {hits}"
        elif unit.unit_type == UnitType.LANCER:
            success = self._resolve_lancer_thrust(unit, target_tile)
            self.log(f"{unit.name} 스킬 사용: {skill.name}")
            if not success and not self.last_feedback:
                self.last_feedback = "관통 돌진이 적에게 닿지 않았습니다."
        self._cleanup_dead_units()
        self._check_victory()
        if self.state == GameState.GAME_OVER:
            self.queue_sound("win")

    def _resolve_charge(self, unit: Unit, target_tile: Position) -> None:
        """검병 돌진 스킬의 이동, 타격, 밀치기 처리를 수행한다."""
        start = unit.position
        dx = 0 if target_tile[0] == unit.position[0] else (1 if target_tile[0] > unit.position[0] else -1)
        dy = 0 if target_tile[1] == unit.position[1] else (1 if target_tile[1] > unit.position[1] else -1)
        target_unit = self.unit_at(target_tile)
        if target_unit and target_unit.team != unit.team:
            landing = (target_tile[0] - dx, target_tile[1] - dy)
            if landing != unit.position and self.unit_at(landing) is None and self.board.is_walkable(landing):
                unit.move(landing)
                self.inspected_unit_id = unit.id
                self.add_effect("dash", landing, duration=0.45, origin=start)
            damage = unit.attack(target_unit)
            self.add_effect("slash", target_unit.position, duration=0.35)
            self._show_damage_feedback(target_unit, damage, source=unit.position, heavy=True)
            target_origin = target_unit.position
            if damage > 0 and target_unit.is_alive() and self._push_unit(target_unit, dx, dy):
                self._advance_into_tile(unit, target_origin, start)
                self.last_feedback = f"{target_unit.name}을 밀어내고 그 자리를 차지했습니다."
            elif damage > 0:
                self.last_feedback = f"돌진으로 {target_unit.name}에게 피해를 주었습니다."
            else:
                self.last_feedback = "돌진이 보호막에 막혔습니다."
        else:
            unit.move(target_tile)
            self.inspected_unit_id = unit.id
            self.add_effect("dash", target_tile, duration=0.45, origin=start)
            self.last_feedback = f"{unit.name}이 돌진으로 전진했습니다."

    def _resolve_piercing_shot(self, unit: Unit, target_tile: Position) -> int:
        """궁수 관통 사격 경로를 따라 맞은 적 수를 계산하고 피해를 준다."""
        dx = 0 if target_tile[0] == unit.position[0] else (1 if target_tile[0] > unit.position[0] else -1)
        dy = 0 if target_tile[1] == unit.position[1] else (1 if target_tile[1] > unit.position[1] else -1)
        hits = 0
        cursor = unit.position
        path: list[Position] = []
        for _ in range(3):
            cursor = (cursor[0] + dx, cursor[1] + dy)
            if not self.board.in_bounds(cursor) or self.board.is_blocked(cursor):
                break
            path.append(cursor)
            target = self.unit_at(cursor)
            if target and target.team != unit.team:
                self._show_damage_feedback(target, target.take_damage(1), source=unit.position)
                hits += 1
        self.add_effect("beam", target_tile, duration=0.32, origin=unit.position, path=path)
        return hits

    def _resolve_terror_slam(self, unit: Unit, target_tile: Position) -> tuple[bool, int]:
        """보스 왕의 순간이동 광역 강타를 처리한다."""
        start = unit.position
        teleported = False
        if self.board.is_walkable(target_tile):
            occupant = self.unit_at(target_tile)
            if occupant is None:
                unit.move(target_tile)
                self.inspected_unit_id = unit.id
                self.add_effect("teleport", target_tile, duration=0.55, origin=start)
                teleported = True
        affected_tiles = [tile for tile in self.board.tiles_in_square(target_tile, 1) if not self.board.is_blocked(tile)]
        self.add_effect("boss_burst", target_tile, duration=0.78, tiles=affected_tiles, origin=start if teleported else unit.position)
        self.add_effect("text", target_tile, duration=0.8, text="공포", color=(255, 92, 92))
        hits = 0
        for tile in affected_tiles:
            target = self.unit_at(tile)
            if target is None or target.team == unit.team:
                continue
            damage = target.take_damage(2)
            self._show_damage_feedback(target, damage, source=unit.position, heavy=True)
            hits += 1
            dx = 0 if target.position[0] == unit.position[0] else (1 if target.position[0] > unit.position[0] else -1)
            dy = 0 if target.position[1] == unit.position[1] else (1 if target.position[1] > unit.position[1] else -1)
            if dx != 0 or dy != 0:
                self._push_unit(target, dx, dy)
        return teleported, hits

    def _resolve_flame_burst(self, unit: Unit, target_tile: Position) -> int:
        """마법사의 범위 폭발 피해를 적용하고 적중 수를 반환한다."""
        hits = 0
        affected_tiles = [tile for tile in self.board.tiles_in_square(target_tile, 1) if not self.board.is_blocked(tile)]
        self.add_effect("burst", target_tile, duration=0.55, tiles=affected_tiles)
        for tile in affected_tiles:
            target = self.unit_at(tile)
            if target and target.team != unit.team:
                self._show_damage_feedback(target, target.take_damage(1), source=unit.position)
                hits += 1
        return hits

    def _resolve_leap_strike(self, unit: Unit, target_tile: Position) -> None:
        """기사의 도약 강타와 후속 밀치기/보호막을 처리한다."""
        start = unit.position
        target = self.unit_at(target_tile)
        self.add_effect("dash", target_tile, duration=0.40, origin=start)
        if target and target.team != unit.team:
            target_origin = target.position
            damage = unit.attack(target, amount=2)
            self._show_damage_feedback(target, damage, source=unit.position, heavy=True)
            if not target.is_alive():
                unit.move(target_tile)
                self.inspected_unit_id = unit.id
                self.last_feedback = f"{unit.name}이 적을 쓰러뜨리고 자리를 차지했습니다."
            else:
                push_dx = 0 if target.position[0] == unit.position[0] else (1 if target.position[0] > unit.position[0] else -1)
                push_dy = 0 if target.position[1] == unit.position[1] else (1 if target.position[1] > unit.position[1] else -1)
                if self._push_unit(target, push_dx, push_dy, distance=2):
                    self._advance_into_tile(unit, target_origin, start)
                    self.last_feedback = f"도약 강타로 {target.name}을 밀어내고 그 자리를 차지했습니다."
                else:
                    self.last_feedback = f"도약 강타는 적중했지만 {target.name}은 더 밀리지 않았습니다."
        else:
            unit.move(target_tile)
            self.inspected_unit_id = unit.id
            unit.shield_turns = max(unit.shield_turns, 1)
            self.add_effect("shield", target_tile, duration=0.55)
            self.last_feedback = f"{unit.name}이 도약 후 1턴 보호막을 얻었습니다."

    def _resolve_bishop_beam(self, unit: Unit, target_tile: Position) -> int:
        """사제 대각 광선 경로에 있는 적에게 피해를 준다."""
        dx = 1 if target_tile[0] > unit.position[0] else -1
        dy = 1 if target_tile[1] > unit.position[1] else -1
        hits = 0
        path: list[Position] = []
        cursor = unit.position
        for _ in range(4):
            cursor = (cursor[0] + dx, cursor[1] + dy)
            if not self.board.in_bounds(cursor) or self.board.is_blocked(cursor):
                break
            path.append(cursor)
            target = self.unit_at(cursor)
            if target and target.team != unit.team:
                self._show_damage_feedback(target, target.take_damage(1), source=unit.position)
                hits += 1
        self.add_effect("beam", target_tile, duration=0.36, origin=unit.position, path=path)
        return hits

    def _resolve_lancer_thrust(self, unit: Unit, target_tile: Position) -> bool:
        """창병 관통 돌진의 전진, 타격, 장거리 밀치기를 처리한다."""
        dx = 0 if target_tile[0] == unit.position[0] else (1 if target_tile[0] > unit.position[0] else -1)
        dy = 0 if target_tile[1] == unit.position[1] else (1 if target_tile[1] > unit.position[1] else -1)
        cursor = unit.position
        path: list[Position] = []
        furthest_open = unit.position
        struck_target: Unit | None = None
        for _ in range(3):
            cursor = (cursor[0] + dx, cursor[1] + dy)
            if not self.board.in_bounds(cursor) or self.board.is_blocked(cursor):
                break
            path.append(cursor)
            target = self.unit_at(cursor)
            if target is None:
                furthest_open = cursor
                continue
            if target.team == unit.team:
                break
            struck_target = target
            break

        if struck_target is None:
            start = unit.position
            if furthest_open != unit.position:
                unit.move(furthest_open)
                self.inspected_unit_id = unit.id
                self.add_effect("dash", furthest_open, duration=0.40, origin=start)
                self.last_feedback = f"{unit.name}이 창을 겨누며 전진했습니다."
            else:
                self.last_feedback = "관통 돌진이 막혀 제자리에서 멈췄습니다."
            self.add_effect("beam", furthest_open, duration=0.28, origin=start, path=path)
            return False

        landing = (struck_target.position[0] - dx, struck_target.position[1] - dy)
        start = unit.position
        if landing != unit.position and self.board.is_walkable(landing) and self.unit_at(landing) is None:
            unit.move(landing)
            self.inspected_unit_id = unit.id
            self.add_effect("dash", landing, duration=0.40, origin=start)
        damage = unit.attack(struck_target)
        self._show_damage_feedback(struck_target, damage, source=unit.position, heavy=True)
        target_origin = struck_target.position
        pushed = struck_target.is_alive() and self._push_unit(struck_target, dx, dy, distance=7)
        if pushed:
            self._advance_into_tile(unit, target_origin, start)
        self.add_effect("beam", struck_target.position, duration=0.28, origin=start, path=path)
        if damage > 0 and pushed:
            self.last_feedback = f"{struck_target.name}을 밀어내고 그 자리를 차지했습니다."
        elif damage > 0:
            self.last_feedback = f"{struck_target.name}을 찌르며 돌진했지만 더 밀어내지는 못했습니다."
        elif pushed:
            self.last_feedback = f"{struck_target.name}의 피해는 막혔지만 밀어내고 그 자리를 차지했습니다."
        else:
            self.last_feedback = "관통 돌진이 적에게 닿았지만 큰 흔들림은 없었습니다."
        return damage > 0 or pushed

    def _show_damage_feedback(
        self,
        target: Unit,
        damage: int,
        source: Position | None = None,
        heavy: bool = False,
    ) -> None:
        """피해 또는 방어 결과에 맞는 전투 이펙트와 떠오르는 텍스트를 만든다."""
        self.inspected_unit_id = target.id
        if damage > 0:
            if source is not None:
                self.add_effect("attack_line", target.position, duration=0.18 if heavy else 0.14, origin=source)
            self.add_effect("attack", target.position, duration=0.45)
            self.add_effect("impact", target.position, duration=0.34, heavy=heavy)
            self.add_effect("hit_flash", target.position, duration=0.20, heavy=heavy)
            self.add_effect("text", target.position, duration=0.85, text=f"-{damage}", color=(255, 120, 120))
        else:
            self.add_effect("shield", target.position, duration=0.45)
            self.add_effect("guard_ring", target.position, duration=0.30)
            self.add_effect("text", target.position, duration=0.80, text="막힘", color=(255, 214, 120))

    def _advance_into_tile(self, unit: Unit, destination: Position, origin: Position) -> None:
        """밀치기나 처치 후 비어진 타일을 차지하도록 유닛을 전진시킨다."""
        if unit.position == destination:
            return
        if not self.board.is_walkable(destination) or self.unit_at(destination) is not None:
            return
        unit.move(destination)
        self.inspected_unit_id = unit.id
        self.add_effect("dash", destination, duration=0.30, origin=origin)

    def _push_unit(self, target: Unit, dx: int, dy: int, distance: int = 1) -> bool:
        """대상을 지정 방향으로 가능한 만큼 밀어내고 성공 여부를 반환한다."""
        last_open_tile: Position | None = None
        for step in range(1, distance + 1):
            push_tile = (target.position[0] + dx * step, target.position[1] + dy * step)
            if not self.board.is_walkable(push_tile) or self.unit_at(push_tile) is not None:
                break
            last_open_tile = push_tile
        if last_open_tile is None:
            return False
        target.move(last_open_tile)
        self.add_effect("move", last_open_tile, duration=0.30)
        return True
