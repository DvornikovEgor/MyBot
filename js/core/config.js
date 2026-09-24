// Глобальные настройки игры «КВАК СРЕДИ НАС» (Among Us с лягушками)
export const CONFIG = {
  worldW: 2100,
  worldH: 1400,

  playerRadius: 15,
  playerSpeed: 168,
  ghostSpeed: 300,

  vision: 330,
  visionFogged: 135, // во время саботажа «Туман»

  killRange: 82,
  killCooldown: 20,
  reportRange: 84,
  ventRange: 62,
  emergencyRange: 70,
  emergencyCooldown: 30,

  taskHoldTime: 4.2,
  tasksPerPlayer: 5,

  sabotageDuration: 26,
  sabotageCooldown: 34,
  fixHoldTime: 3.0,

  ventHideTime: 9,

  discussionTime: 24,
  votingTime: 20,
  ejectTime: 4.5,

  botThink: 0.25,
  botSeeBody: 420,
  botWitnessRange: 300,
};

export const ROLES = {
  CREW: 'crew',
  IMPOSTOR: 'impostor',
};

export const FROG_NAMES = [
  'Квакс', 'Жабыч', 'Пруди', 'Росинка', 'Головастик', 'Комарик',
  'Слизняк', 'Кувшинка', 'Ух-Ух', 'Мухоед', 'Тина', 'Пузырь',
  'Болотник', 'Кочкин', 'Ряска', 'Пиявка',
];

export const SUITS = [
  { id: 'green',   name: 'Зелёный',    body: '#4caf50', dark: '#2f7d33', belly: '#bfe8a8' },
  { id: 'blue',    name: 'Голубой',    body: '#3aa7dc', dark: '#22709b', belly: '#b8e6f7' },
  { id: 'red',     name: 'Красный',    body: '#e74c3c', dark: '#a5301f', belly: '#f6b8a8' },
  { id: 'yellow',  name: 'Жёлтый',     body: '#f1c40f', dark: '#b48f05', belly: '#fbeaa6' },
  { id: 'pink',    name: 'Розовый',    body: '#f072b6', dark: '#b8467f', belly: '#fbd4e8' },
  { id: 'orange',  name: 'Оранжевый',  body: '#f39c12', dark: '#b76f06', belly: '#fbdda6' },
  { id: 'violet',  name: 'Фиолетовый', body: '#9b59b6', dark: '#6d3a85', belly: '#e0c6ee' },
  { id: 'teal',    name: 'Бирюзовый',  body: '#1abc9c', dark: '#10836c', belly: '#b4efe2' },
  { id: 'brown',   name: 'Коричневый', body: '#8d6e63', dark: '#5d443c', belly: '#ddc6b8' },
  { id: 'white',   name: 'Белый',      body: '#ecf0f1', dark: '#a9b2b5', belly: '#ffffff' },
  { id: 'lime',    name: 'Лаймовый',   body: '#aeea00', dark: '#79a300', belly: '#e6f7a8' },
  { id: 'navy',    name: 'Тёмно-синий', body: '#3f51b5', dark: '#28357a', belly: '#c2caf0' },
];
