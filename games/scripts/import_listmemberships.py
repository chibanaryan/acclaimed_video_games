from .. import models


def run(*args):
    txt_path = args[0]

    for rank, line in enumerate(open(txt_path)):
        bits = line.strip().split('\t')
        game = models.Game.objects.get(rank=rank+1)
        print(game)
        for bit in bits:
            list_id, position = [int(x) for x in bit.split(':')]
            print(list_id, position)
            source_list = models.List.objects.get(id=list_id+1)
            models.ListMembership.objects.update_or_create(
                list=source_list,
                game=game,
                defaults={
                    'rank': position,
                }
            )
