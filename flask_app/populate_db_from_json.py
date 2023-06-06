"""
This script will use the published_articles.json file to populate the User and DataSet 
objects of the symportal.org databse.
It will also check to make sure that anychanges made to the published_articles.json are reflected
in the database. However, this will not include the deletion of objects. Although
it will include removal of items from objects' lists.
"""

from sp_app import db
from sp_app.models import User, DataSet
import json

class PopulateDBFromJson:
    def __init__(self):
        self.path_to_json = 'published_articles.json'
        self.json_dataset_objects, self.json_user_objects = self._get_json_array()

    def _get_json_array(self):
        with open('published_articles.json', 'r') as f:
            return json.load(f)

    def populate_db(self):
        # Populate the db with dataset objects
        for json_ds_obj in self.json_dataset_objects:
            ds_query = DataSet.query.filter_by(data_name=json_ds_obj['data_name']).first()
            if not ds_query:
                ds = DataSet(
                    data_name=json_ds_obj['data_name'], study_name=json_ds_obj['study_name'],
                    study_to_load_str=json_ds_obj['study_to_load_str'], title=json_ds_obj['title'],
                    location=json_ds_obj['location'], num_samples=int(json_ds_obj['num_samples']),
                    additional_markers=json_ds_obj['additional_markers'], is_published=json_ds_obj['is_published'],
                    run_type=json_ds_obj['run_type'], article_url=json_ds_obj['article_url'],
                    seq_data_url=json_ds_obj['seq_data_url'], data_explorer=json_ds_obj['data_explorer'],
                    analysis=json_ds_obj['analysis'], author_list_string=json_ds_obj['author_list_string']
                )
                db.session.add(ds)
                print(f'\n\nAdding DataSet {ds} to the database')
            else:
                print(f'\n\nDataSet {ds_query} already exists')
                print(f'Verifying that no changes have been made to {ds_query}')
                changed=False
                for attr in ['study_name', 'study_to_load_str', 'title', 'location',
                             'num_samples', 'additional_markers', 'is_published', 'run_type',
                             'article_url', 'seq_data_url', 'data_explorer', 'analysis', 'author_list_string']:
                    if attr in ['num_samples']:
                        if getattr(ds_query, attr) != int(json_ds_obj[attr]):
                            changed = True
                            print(f'Changing DataSet.{attr} {getattr(ds_query, attr)} --> {json_ds_obj[attr]} for {ds_query}')
                            setattr(ds_query, attr, json_ds_obj[attr])
                    else:
                        if getattr(ds_query, attr) != json_ds_obj[attr]:
                            changed = True
                            print(f'Changing DataSet.{attr} {getattr(ds_query, attr)} --> {json_ds_obj[attr]} for {ds_query}')
                            setattr(ds_query, attr, json_ds_obj[attr])
                if not changed:
                    print(f'No changes made to {ds_query}')

        # Populate the db with user objects
        for json_user_obj in self.json_user_objects:
            user_query = User.query.filter_by(username=json_user_obj['username']).first()
            if not user_query:
                u = User(username=json_user_obj['username'], is_admin=json_user_obj['is_admin'])
                db.session.add(u)
                print(f'\n\nAdding User {u} to the databse')
            else:
                print(f'\n\nUser {user_query} already exists')
                print(f'Verifying that no changes have been made to {user_query}')
                if user_query.is_admin != json_user_obj["is_admin"]:
                    print(f'Changing DataSet.is_admin {user_query.is_admin} --> {json_user_obj["is_admin"]} for {user_query}')
                else:
                    print(f'No changes made to {user_query}')

        # At this point we have the dataset and user objects
        # populated in the db
        # Now do the relationships between them
        for json_ds_obj in self.json_dataset_objects:
            ds_obj = DataSet.query.filter_by(data_name=json_ds_obj['data_name']).first()
            if not ds_obj:
                raise RuntimeError(f"Unable to find the DataSet object matching the data_name {json_ds_obj['data_name']}")

            # Get a set of the usernames that should be associated
            should_be_assoc = set(json_ds_obj['users_with_access'])
            # Get a set of the usernames that are associated
            are_assoc = set([usr.username for usr in ds_obj.users_with_access.all()])
            if should_be_assoc == are_assoc:
                print(f'\n\n{ds_obj} users_with_access list is up to date')
            else:
                # Get the list of usernames of users that need to be added and removed
                need_to_be_added = [usr for usr in should_be_assoc if usr not in are_assoc]
                need_to_be_removed = [usr for usr in are_assoc if usr not in should_be_assoc]
                # Add those that need to be added
                for usr_to_add in need_to_be_added:
                    u = User.query.filter_by(username=usr_to_add).first()
                    if not u:
                        raise RuntimeError(f'Unable to find User object matching user name {usr_to_add}')
                    else:
                        # The add_author method instigates checks to see if the user
                        # object is already listed in the users_with_access list of the
                        # dataset object
                        if ds_obj.add_user_authorisation(u):
                            print(f'\n\nAdding {u} to the users_with_access list for {ds_obj}')
                        else:
                            raise RuntimeError(f'We are being told that the user already exists in the DataSet'
                                               f'object, despite having checked that it didnt. Something is wrong.')

                # Add those that need to be added
                for usr_to_remove in need_to_be_removed:
                    u = User.query.filter_by(username=usr_to_remove).first()
                    if not u:
                        raise RuntimeError(f'Unable to find User object matching user name {usr_to_remove}')
                    else:
                    # The add_author method instigates checks to see if the user
                    # object is already listed in the users_with_access list of the
                    # dataset object
                        if ds_obj.remove_user_authorisation(u):
                            print(f'Removing {u} from the users_with_access list for {ds_obj}')
                        else:
                            raise RuntimeError(f'We are being told that the user does not exists in the DataSet'
                                               f'object, despite having checked that it did. Something is wrong.')



        for json_user_obj in self.json_user_objects:
            user_obj = User.query.filter_by(username=json_user_obj['username']).first()
            if not user_obj:
                raise RuntimeError(f"Unable to find the User object matching the data_name {json_user_obj['username']}")

            # Get a set of the usernames that should be associated
            should_be_assoc = set(json_user_obj['data_sets'])
            # Get a set of the usernames that are associated
            are_assoc = set([ds.study_to_load_str for ds in user_obj.datasets.all()])
            if should_be_assoc == are_assoc:
                print(f'\n\n{user_obj} datasets list is up to date')
            else:
                # Get the list of usernames of users that need to be added and removed
                need_to_be_added = [ds for ds in should_be_assoc if ds not in are_assoc]
                need_to_be_removed = [ds for ds in are_assoc if ds not in should_be_assoc]

                # Add those that need to be added
                for ds_to_add in need_to_be_added:
                    ds_obj = DataSet.query.filter_by(study_to_load_str=ds_to_add).first()
                    if not ds_obj:
                        raise RuntimeError(f'Unable to find DataSet object matching study_to_load_str {ds_to_add}')
                    else:
                        if user_obj.add_authorisation_for_dataset(ds_obj):
                            print(f'\n\nAdding {ds_obj} to the datasets list for {user_obj}')
                        else:
                            raise RuntimeError(f'We are being told that the dataset already exists in the User'
                                               f'object, despite having checked that it didnt. Something is wrong.')

                # Add those that need to be added
                for ds_to_remove in need_to_be_removed:
                    ds_obj = DataSet.query.filter_by(study_to_load_str=ds_to_remove).first()
                    if not ds_obj:
                        raise RuntimeError(f'Unable to find DataSet object matching study_to_load_str {ds_to_remove}')
                    else:
                        if user_obj.remove_authorisation_for_dataset(ds_obj):
                            print(f'Removing {ds_obj} from the dataset list for {user_obj}')
                        else:
                            raise RuntimeError(f'We are being told that the dataset does not exists in the User'
                                               f'object, despite having checked that it did. Something is wrong.')


        db.session.commit()




pdbfj = PopulateDBFromJson()
pdbfj.populate_db()