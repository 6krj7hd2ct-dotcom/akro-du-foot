-- Correctifs ciblés des photos Hall of Fame.
-- Non destructif : aucune suppression, aucun changement d'identité ou de palmarès.

with photo_fixes(name, photo_url) as (
  values
    ('Neymar', 'https://images.fotmob.com/image_resources/playerimages/19533.png'),
    ('Karim Benzema', 'https://images.fotmob.com/image_resources/playerimages/26166.png'),
    ('Luka Modrić', 'https://images.fotmob.com/image_resources/playerimages/31097.png'),
    ('Kaká', 'https://commons.wikimedia.org/wiki/Special:FilePath/Kak%C3%A1.jpg?width=500'),
    ('Robert Lewandowski', 'https://images.fotmob.com/image_resources/playerimages/93447.png'),
    ('Zlatan Ibrahimović', 'https://images.fotmob.com/image_resources/playerimages/35724.png'),
    ('Didier Drogba', 'https://images.fotmob.com/image_resources/playerimages/30822.png'),
    ('Pelé', 'https://commons.wikimedia.org/wiki/Special:FilePath/Pele%20con%20brasil%20(cropped).jpg?width=500'),
    ('Romário', 'https://commons.wikimedia.org/wiki/Special:FilePath/Salvaromariobrasil.jpg?width=500'),
    ('Ferenc Puskás', 'https://commons.wikimedia.org/wiki/Special:FilePath/Ferenc%20Pusk%C3%A1s%20(cropped).jpg?width=500'),
    ('Marco van Basten', 'https://commons.wikimedia.org/wiki/Special:FilePath/Marco%20van%20Basten%201989%20crop.jpg?width=500'),
    ('Michel Platini', 'https://commons.wikimedia.org/wiki/Special:FilePath/Michel%20Platini%202008.jpg?width=500'),
    ('Johan Cruyff', 'https://commons.wikimedia.org/wiki/Special:FilePath/Johan%20Cruyff%201974c.jpg?width=500'),
    ('Ronaldo Nazário', 'https://images.fotmob.com/image_resources/playerimages/93179.png'),
    ('Fabio Cannavaro', 'https://images.fotmob.com/image_resources/playerimages/34520.png'),
    ('Ronaldinho', 'https://images.fotmob.com/image_resources/playerimages/30743.png'),
    ('Pavel Nedvěd', 'https://images.fotmob.com/image_resources/playerimages/30725.png'),
    ('Luís Figo', 'https://images.fotmob.com/image_resources/playerimages/30696.png'),
    ('Rivaldo', 'https://images.fotmob.com/image_resources/playerimages/39728.png'),
    ('Zinedine Zidane', 'https://images.fotmob.com/image_resources/playerimages/38422.png')
)
update public.hall_of_fame_players hof
set
  photo_url = photo_fixes.photo_url,
  last_enriched_at = coalesce(hof.last_enriched_at, now()),
  updated_at = now()
from photo_fixes
where hof.name = photo_fixes.name
   or hof.display_name = photo_fixes.name;
