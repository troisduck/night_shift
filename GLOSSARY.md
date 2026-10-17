# «Ночная смена» — глоссарий перевода

Один термин — один перевод на всю игру. Новый термин сначала сюда, потом в `STRINGS.en`. Колонка «Где» — ключи или места, где термин встречается чаще всего. Орфография — американская (color, center). Кавычки в английском — “…”, апостроф — ’.

## Станция и люди

| Русский | English | Где | Комментарий |
|---|---|---|---|
| БЩУ, блочный щит управления | main control room (MCR); в тексте — control room | `jr.top`, `shifts.sub`, `sign.doc2.h2` | «Оперативный журнал БЩУ-1» → Control Room 1 operating log |
| ВВЭР | VVER | `moment.blast` | так пишут в английских источниках |
| энергоблок | (power) unit | `door.plate.unit`, `shifts.sub`, `mm.title` | «Энергоблок 1» → Unit 1 |
| стажёр-оператор | trainee operator | `sign.fill`, `jr.sign.meRole`, `sign.trainee` | |
| начальник смены | shift supervisor | `mentor.name`, `jr.sign.bossRole` | высшее звание в 2.0 — тоже shift supervisor |
| Палыч | Palych | `mentor.name`, `note.who`, `ui.what` | имя не переводится; в подсказке «Вызов» один раз сказано, что это прозвище по отчеству (Pavlovich) |
| сменщик | the last shift | `lv.xenon.brief.2` | «Сменщик поднял стержни» → The last shift pulled the rods |
| диспетчер | dispatch, dispatcher | `tip.demandUp`, `ui.mwe`, `ui.sched` | реплика по телефону начинается с «Dispatch:» |
| посёлок | the town | `intro.*`, `ui.window` | |
| смена (в мире, вместо «уровня») | shift | везде | «Смена N из 9» → Shift N of 9; «смена сдана» → shift handed over; «смена прервана» → shift cut short |
| Без страховки | No Safety Net | `lv.hardcore.title`, `shifts.hard` | |
| Я опытный (рычаг) | Experienced | `shifts.knife`, `tip.knife` | |
| Личное дело | Personnel File | `sign.folder` | |
| Приёмка смены (2.0) | Shift Handover | — | ещё нет в игре |
| Подготовка тренажёра (2.0) | Simulator Setup | — | ещё нет в игре |
| Заморозка тренажёра (2.0) | Simulator Freeze | — | ещё нет в игре |
| Работа без нарушений (2.0) | Incident-Free Operation | — | ещё нет в игре |

## Реактор и первый контур

| Русский | English | Где | Комментарий |
|---|---|---|---|
| стержни (регулирующие) | control rods; на щите — Rods | `desk.rods`, `ui.rods` | кнопки ВВЕРХ / ВНИЗ → UP / DOWN |
| погружены (стержни, %) | inserted | `desk.rods.unit` | 0% — стержни наверху, 100% — внизу |
| рабочая зона (стержней) | working band | `tip.rodsZone`, `cond.rodsZone`, `lamp.rods` | |
| АЗ, аварийная защита | reactor trip (SCRAM); на кнопке, шильде и в журнале — SCRAM | `desk.scram*`, `lamp.scram`, `why.*.title` | выбран SCRAM, а не TRIP: узнаваемо и коротко. Событие — a scram, «сработала АЗ» → the reactor scrammed / Reactor scram |
| автоматическая защита, защиты | automatic protection, protections | `desk.prot`, `prot.*` | «защиты выведены / введены» → protections are out / back in |
| ключ вывода защит | protection bypass key | `desk.prot.key`, `ui.prot` | |
| уставка | setpoint | `prot.onTrip` | |
| пломба | seal | `prot.seal`, `log.seal` | |
| Разгон (шкала, график) | Rate | `desk.rate`, `ui.rate`, `chart.rho` | у настоящего щита близкий прибор — startup rate; новичку хватает «Rate» |
| мощность реактора | reactor power | `desk.power`, `ui.power` | |
| остаточное тепло | decay heat | `desk.decay`, `tip.decayInfo`, `lv.blackout.*` | «распад осколков деления» → fission products decaying |
| реактивность | reactivity | `tip.xenonDecay` | |
| ксенон, йодная яма | xenon, xenon pit | `lv.xenon.*`, `lamp.xenon` | «Йодная яма» → Xenon Pit: у игрока на щите прибор «Xenon»; «отравление ксеноном» → xenon poisoning |
| борная кислота, бор | boric acid, boron | `ui.boron`, `desk.boron` | кнопки ДОБАВИТЬ / РАЗБАВИТЬ → ADD / DILUTE |
| ГЦН, главные насосы | reactor coolant pumps (RCP); на шильде — RCP-1…4, на панели — Coolant pumps | `pump.name`, `desk.pumps`, `ui.pumps` | состояния: работает / разгон / выбег / отключён / авария / нет питания → running / starting / coasting / off / fault / no power |
| отказ насоса | pump failure; в журнале — RCP-N trip | `lamp.pump`, `log.pumpTrip`, `lv.pump.title` | |
| вода на выходе | outlet water | `desk.tout`, `ui.tout` | на входе → inlet |
| запас до кипения | margin to boiling | `ui.margin`, `desk.margin` | |
| давление в контуре | loop pressure | `ui.pressure`, `chart.pressure` | |
| компенсатор давления | pressurizer | `grp.pressure`, `ui.heater`, `mm.pzr.1` | |
| нагрев / впрыск | heaters / spray | `desk.heat`, `desk.spray` | на кнопках — HEATERS / SPRAY |
| предохранительный клапан | relief valve | `lamp.phigh.tip` | в коде клапан открывается на 18 МПа и стравливает давление до уставки — по смыслу relief valve |
| активная зона | core | `why.damage.*`, `prot.off` | повреждение активной зоны → core damage |
| гермооболочка | containment shell | `moment.blast` | |

## Второй контур, сеть, электрика

| Русский | English | Где | Комментарий |
|---|---|---|---|
| парогенератор (ПГ) | steam generator (SG) | `mm.sg`, `lamp.sg` | |
| подпитка | feedwater | `tip.dgOnline`, `lamp.sg.tip` | |
| клапан турбины | turbine valve | `desk.valve`, `ui.valve` | кнопки ПРИКРЫТЬ / ОТКРЫТЬ → CLOSE / OPEN |
| сброс пара | steam dump | `lamp.dump`, `mm.dump` | в атмосферу → to atmosphere |
| конденсатор | condenser | `mm.cond` | |
| генератор, в сети | generator, on grid | `desk.grid`, `desk.online` | |
| задание (диспетчера) | target | `desk.demand`, `run.demand`, `ui.mwe` | «отклонение от задания» → load off target |
| график диспетчера | dispatch schedule | `ui.sched`, `lv.peak.*` | |
| нагрузка | load | `lv.peak.goal`, `why.schedule.*` | |
| дизель-генераторы, ДГ | diesel generators, DG | `desk.dg`, `ui.dg` | кнопка ПУСК ДГ → START DG; «дизели в работе» → diesels running |
| обесточивание, нет сети, внешнее питание | station blackout / loss of off-site power; на табло — No grid | `lamp.offsite`, `lv.blackout.*` | смена «Блэкаут» → Blackout |
| резервная автоматика | backup automatics | `why.backup.*` | |
| потребители (на мнемосхеме) | consumers | `mm.city` | |

## Щит и сигнализация

| Русский | English | Где | Комментарий |
|---|---|---|---|
| табло (сигнализации) | annunciator (panel) | `ann.aria`, `tip.ackHint` | окно табло → (annunciator) window |
| квитировать, «Квитирование» | acknowledge; на кнопке — ACK | `ann.ack`, `ui.ack`, `tip.ackHint` | |
| предупредительная / аварийная сигнализация | warning / alarm | — | |
| мнемосхема | mimic diagram; на плакате — UNIT MIMIC DIAGRAM | `mm.*`, `ui.mimic` | |
| самописец, лента | chart recorder, strip | `jr.tape`, `tip.chart` | |
| шильда, табличка | nameplate, plate | — | |
| заглушка / пустое гнездо | instrument not installed yet / empty bay | `tip.cover.*` | бирка «ввод в работу · смена N» → commissioning · shift N |
| клеймо ОТК, ПНС- | QC, PNL- | `tex.qc`, `tex.code` | ОТК — отдел технического контроля → QC (quality control) |
| задание (табло задания) | task; лампа «в цели» → on target | `top.goal`, `top.inGoal`, `ui.goal` | |
| Задание на смену (бланк) | Shift assignment | `css.form` | |
| журнал смены, «Зачтено» | operating log, Passed | `jr.*` | «не зачтено» → not passed |
| Вызов (кнопка селектора) | Call | `mentor.call`, `ui.what` | |
| слой игры: пауза, скорость, громкость, заново, смены | Pause, ×1/×2/×4, Vol., Restart, Shifts | `top.*` | клавиша «Пробел» → Space |

## Решения, где перевод — не дословный

- **«Даёшь ток»** → *Lights On*: советский лозунг не переводится; в смене город впервые получает свет.
- **«Так держать»** → *Steady as she goes*.
- **«Если запахло жареным»** → *If things go south*.
- **«Снимаю каску»** → *I take my hard hat off to you*.
- **«Пломбу я не видел»** → *I never saw that seal*.
- **«Можете это не читать: на море в Египет вы всё равно больше не поедете»** → *You may skip this: you won’t be taking beach holidays abroad any more anyway* — шутка про ограничения на выезд с допуском; Египет для англоязычного игрока ничего не значит, смысл сохранён без него.
- **«Не говорить «Ой»»** → *Not to say “oops”*.
- **«Вот это реакция!», «Неплохо для первой ночи!»** — восклицательные знаки убраны: похвала Палыча по-английски сухая (*That’s how you react.*, *Not bad for a first night.*).
- **Трафарет «НАЧАТЬ ИГРУ»** → *START GAME*; перемычки у букв с замкнутой серединой — `LANG_META.en.stencil`.
