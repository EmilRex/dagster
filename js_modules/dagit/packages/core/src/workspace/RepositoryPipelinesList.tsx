import {useQuery} from '@apollo/client';
import {Box, NonIdealState} from '@dagster-io/ui';
import * as React from 'react';

import {useTrackPageView} from '../app/analytics';
import {isHiddenAssetGroupJob} from '../asset-graph/Utils';
import {graphql} from '../graphql';
import {PipelineTable} from '../pipelines/PipelineTable';

import {repoAddressAsHumanString} from './repoAddressAsString';
import {repoAddressToSelector} from './repoAddressToSelector';
import {RepoAddress} from './types';

const REPOSITORY_PIPELINES_LIST_QUERY = graphql(`
  query RepositoryPipelinesListQuery($repositorySelector: RepositorySelector!) {
    repositoryOrError(repositorySelector: $repositorySelector) {
      __typename
      ... on Repository {
        id
        pipelines {
          id
          ...PipelineTableFragment
        }
      }
      ... on RepositoryNotFoundError {
        message
      }
    }
  }
`);

interface Props {
  repoAddress: RepoAddress;
  display: 'jobs' | 'pipelines';
}

export const RepositoryPipelinesList: React.FC<Props> = (props) => {
  useTrackPageView();

  const {display, repoAddress} = props;
  const repositorySelector = repoAddressToSelector(repoAddress);

  const {data, error, loading} = useQuery(REPOSITORY_PIPELINES_LIST_QUERY, {
    variables: {repositorySelector},
  });

  const repo = data?.repositoryOrError;
  const pipelinesForTable = React.useMemo(() => {
    if (!repo || repo.__typename !== 'Repository') {
      return null;
    }
    return repo.pipelines
      .filter((pipelineOrJob) => !isHiddenAssetGroupJob(pipelineOrJob.name))
      .map((pipelineOrJob) => ({
        pipelineOrJob,
        repoAddress,
      }))
      .filter(({pipelineOrJob}) =>
        display === 'jobs' ? pipelineOrJob.isJob : !pipelineOrJob.isJob,
      );
  }, [display, repo, repoAddress]);

  if (loading) {
    return null;
  }

  const repoName = repoAddressAsHumanString(repoAddress);

  if (error || !pipelinesForTable) {
    return (
      <Box padding={{vertical: 64}}>
        <NonIdealState
          icon="error"
          title="Unable to load pipelines"
          description={`Could not load pipelines for ${repoName}`}
        />
      </Box>
    );
  }

  if (!pipelinesForTable.length) {
    return (
      <Box padding={64}>
        <NonIdealState
          icon="job"
          title={display === 'jobs' ? 'No jobs found' : 'No pipelines found'}
          description={
            <div>
              {display === 'jobs'
                ? `${repoName} does not have any jobs defined.`
                : `${repoName} does not have any pipelines defined.`}
            </div>
          }
        />
      </Box>
    );
  }

  return <PipelineTable pipelinesOrJobs={pipelinesForTable} showRepo={false} />;
};
